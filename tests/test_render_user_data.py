import argparse
import base64
import importlib.util
import pathlib
import os
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDERER_PATH = REPO_ROOT / "scripts" / "render_user_data.py"
SPEC = importlib.util.spec_from_file_location("render_user_data", RENDERER_PATH)
assert SPEC is not None and SPEC.loader is not None
render_user_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_user_data)


class TailscaleAuthKeyTest(unittest.TestCase):
    def test_bootstrap_reads_cloud_init_decoded_auth_key(self) -> None:
        auth_key = "tskey-auth-test-example"
        args = argparse.Namespace(
            tailscale_auth_key=auth_key,
            with_cyber=False,
            with_t3code=False,
        )

        write_files = render_user_data.optional_write_files(args)
        encoded_content = next(
            line.split("content: ", 1)[1]
            for line in write_files.splitlines()
            if "content: " in line
        )

        self.assertEqual(base64.b64decode(encoded_content).decode(), auth_key)
        self.assertIn(
            'tailscale up --auth-key="$(cat /run/cloud-init/tailscale-auth-key)"',
            render_user_data.optional_bootstrap(args),
        )


class SeshPickerTest(unittest.TestCase):
    def test_render_embeds_picker_and_config_for_custom_user(self) -> None:
        rendered = render_user_data.render(argparse.Namespace(
            admin_user="student", ssh_authorized_key="ssh-ed25519 test",
            tailscale_auth_key=None, with_cyber=False, with_t3code=False,
        ))
        for target, source in ((".local/bin/s", "s"), (".config/sesh/sesh.toml", "sesh.toml")):
            block = rendered.split(f"  - path: /home/student/{target}\n", 1)[1].split("  - path:", 1)[0]
            encoded = next(line.split("content: ", 1)[1] for line in block.splitlines() if "content: " in line)
            self.assertEqual(base64.b64decode(encoded), (REPO_ROOT / "dotfiles" / source).read_bytes())
            self.assertIn("owner: student:student", block)
        self.assertNotIn("__SESH_", rendered)

    def test_picker_preserves_spaces_and_handles_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sesh = root / "sesh"
            sesh.write_text('#!/bin/bash\nif [[ "$1" == list ]]; then echo Home; else printf "%s" "$2" > "$PICKER_RESULT"; fi\n')
            sesh.chmod(0o755)
            picker = root / "fzf-tmux"
            picker.write_text('#!/bin/bash\ncat >/dev/null\nprintf "%s" "$PICKER_SELECTION"\nexit "$PICKER_STATUS"\n')
            picker.chmod(0o755)
            result_path = root / "result"
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", PICKER_RESULT=str(result_path))
            for status, selection, expected in (("0", "project with spaces", 0), ("130", "", 0), ("2", "", 2)):
                with self.subTest(status=status):
                    result_path.unlink(missing_ok=True)
                    result = subprocess.run(["bash", str(REPO_ROOT / "dotfiles" / "s")], env=dict(env, PICKER_STATUS=status, PICKER_SELECTION=selection))
                    self.assertEqual(result.returncode, expected)
                    if selection:
                        self.assertEqual(result_path.read_text(), selection)
                    else:
                        self.assertFalse(result_path.exists())


if __name__ == "__main__":
    unittest.main()
