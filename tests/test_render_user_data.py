import argparse
import base64
import importlib.util
import pathlib
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


if __name__ == "__main__":
    unittest.main()
