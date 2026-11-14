"""Exercise the real picker with fake sesh/fzf commands and a real timeout."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


PICKER = pathlib.Path(__file__).resolve().parents[1] / "dotfiles" / "s"
TIMEOUT = shutil.which("timeout") or shutil.which("gtimeout")


@unittest.skipUnless(TIMEOUT, "Install GNU coreutils for timeout/gtimeout")
class PickerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.result = self.root / "result"
        self.reloads = self.root / "reloads"
        (self.root / "bash").symlink_to("/bin/bash")
        self.env = dict(os.environ, PATH=str(self.root),
                        PICKER_RESULT=str(self.result), RELOAD_RESULT=str(self.reloads),
                        MODE="ok", PICKER_STATUS="0", PICKER_SELECTION="project with spaces",
                        SHELL="/bin/sh")
        (self.root / "timeout").symlink_to(TIMEOUT)
        self.write_command("sesh", '''#!/bin/bash
if [[ "$1" == connect ]]; then
  /bin/sleep "${CONNECT_SLEEP:-0}"
  printf '%s' "$2" > "$PICKER_RESULT"
  exit "${CONNECT_STATUS:-0}"
fi
case "$MODE" in
  stall) exec /bin/sleep 15 ;;
  partial) printf 'saved row\\n'; exec /bin/sleep 15 ;;
  fail) exit "${LIST_STATUS:-42}" ;;
  bulk) for ((i=0; i<10000; i++)); do printf 'project with a long name %s\\n' "$i"; done ;;
  *) printf 'Home\\n' ;;
esac
''')
        self.write_command("fzf-tmux", f'''#!{sys.executable}
import json, os, pathlib, subprocess, sys
rows = "" if os.environ.get("SKIP_READ") else sys.stdin.read()
pathlib.Path(os.environ["PICKER_RESULT"] + ".input").write_text(rows)
if os.environ.get("TEST_RELOADS"):
    results = []
    for arg in sys.argv[1:]:
        if "+reload(" not in arg or "ctrl-f:" in arg:
            continue
        command = arg.split("+reload(", 1)[1][:-1]
        env = dict(os.environ, MODE=os.environ.get("RELOAD_MODE", "ok"))
        # tmux's server need not inherit functions exported by the calling shell.
        env = {{key: value for key, value in env.items() if not key.startswith("BASH_FUNC_")}}
        result = subprocess.run([os.environ["SHELL"], "-c", command],
                                env=env, capture_output=True, text=True, timeout=7)
        results.append([arg.split(":", 1)[0], result.returncode, result.stdout])
    pathlib.Path(os.environ["RELOAD_RESULT"]).write_text(json.dumps(results))
sys.stdout.write(os.environ["PICKER_SELECTION"])
sys.exit(int(os.environ["PICKER_STATUS"]))
''')

    def write_command(self, name, content):
        path = self.root / name
        path.unlink(missing_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def run_picker(self, *args, **env):
        return subprocess.run(["/bin/bash", str(PICKER), *args],
                              env=dict(self.env, **env), capture_output=True,
                              text=True, timeout=7)

    def test_stalled_initial_list_still_allows_selection(self):
        start = time.monotonic()
        result = self.run_picker(MODE="stall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(time.monotonic() - start, 6.5)
        self.assertEqual(self.result.read_text(), "project with spaces")
        self.assertEqual(pathlib.Path(str(self.result) + ".input").read_text().strip(), "")

    def test_timeout_preserves_emitted_rows(self):
        result = self.run_picker(MODE="partial", PICKER_SELECTION="saved row")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result.read_text(), "saved row")
        self.assertIn("saved row", pathlib.Path(str(self.result) + ".input").read_text())

    def test_real_listing_failures_propagate_even_status_one(self):
        for status in (1, 42, 127, 130):
            with self.subTest(status=status):
                result = self.run_picker(MODE="fail", LIST_STATUS=str(status))
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertFalse(self.result.exists())

    def test_picker_selection_cancellation_and_failure(self):
        for status, selection, expected in ((0, "project with spaces", 0),
                                             (0, "", 0), (1, "", 0),
                                             (130, "", 0), (2, "", 2), (124, "", 124)):
            with self.subTest(status=status, selection=selection):
                self.result.unlink(missing_ok=True)
                result = self.run_picker(PICKER_STATUS=str(status), PICKER_SELECTION=selection)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(self.result.read_text() if self.result.exists() else "", selection)

    def test_reload_commands_work_in_subprocess_shell(self):
        for mode, status, output in (("ok", 0, "Home\n"), ("fail", 42, ""),
                                     ("fail", 1, ""), ("fail", 130, "")):
            result = self.run_picker(TEST_RELOADS="1", RELOAD_MODE=mode, LIST_STATUS=str(status))
            self.assertEqual(result.returncode, 0, result.stderr)
            reloads = json.loads(self.reloads.read_text())
            self.assertEqual({row[0] for row in reloads}, {"ctrl-a", "ctrl-t", "ctrl-g", "ctrl-x"})
            self.assertTrue(all(row[1:] == [status, output] for row in reloads), reloads)

    def test_stalled_reloads(self):
        # Each reload gets its own five-second deadline.
        self.env["TEST_RELOADS"] = "1"
        self.env["RELOAD_MODE"] = "stall"
        # Four independent five-second reloads take about twenty seconds in total.
        result = subprocess.run(["/bin/bash", str(PICKER)], env=self.env,
                                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        reloads = json.loads(self.reloads.read_text())
        self.assertTrue(all(row[1:] == [0, ""] for row in reloads), reloads)

    def test_reload_script_path_preserves_spaces_and_apostrophes(self):
        directory = self.root / "picker's directory"
        directory.mkdir()
        picker = directory / "s"
        shutil.copy(PICKER, picker)
        result = subprocess.run(["/bin/bash", str(picker)],
                                env=dict(self.env, TEST_RELOADS="1"),
                                capture_output=True, text=True, timeout=7)
        self.assertEqual(result.returncode, 0, result.stderr)
        reloads = json.loads(self.reloads.read_text())
        self.assertTrue(all(row[1:] == [0, "Home\n"] for row in reloads), reloads)

    def test_gtimeout_fallback(self):
        (self.root / "timeout").unlink()
        (self.root / "gtimeout").symlink_to(TIMEOUT)
        result = self.run_picker()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_connect_bypasses_timeout_and_preserves_status(self):
        # A broken timeout must never affect either route into interactive connect.
        self.write_command("timeout", "#!/bin/sh\nexit 99\n")
        result = self.run_picker("direct project", CONNECT_STATUS="23")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.result.read_text(), "direct project")
        (self.root / "timeout").unlink()
        (self.root / "timeout").symlink_to(TIMEOUT)
        result = self.run_picker(CONNECT_STATUS="124")
        self.assertEqual(result.returncode, 124)

    def test_interactive_connect_can_exceed_five_seconds(self):
        for args in ((), ("direct project",)):
            with self.subTest(args=args):
                result = self.run_picker(*args, CONNECT_SLEEP="5.2")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_timeout_reports_dependency(self):
        (self.root / "timeout").unlink()
        result = self.run_picker()
        self.assertEqual(result.returncode, 127)
        self.assertIn("install coreutils", result.stderr)
        self.assertFalse(self.result.exists())

    def test_listing_timeout_still_allows_cancellation(self):
        result = self.run_picker(MODE="fail", LIST_STATUS="124", PICKER_STATUS="130",
                                 PICKER_SELECTION="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.result.exists())

    def test_early_picker_exit_does_not_override_selection(self):
        result = self.run_picker(MODE="bulk", SKIP_READ="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result.read_text(), "project with spaces")


if __name__ == "__main__":
    unittest.main()
