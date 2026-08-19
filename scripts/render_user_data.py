#!/usr/bin/env python3
"""Render the cloud-init user-data file for a personal Ubuntu VM."""

from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / "templates" / "user-data.yaml.tmpl"
DEFAULT_OUTPUT = REPO_ROOT / "user-data.yaml"
USERNAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]*$")


def base64_encode(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode()
    return base64.b64encode(value).decode()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render cloud-init user-data with selected optional features."
    )
    parser.add_argument(
        "--admin-user",
        default="lents",
        help="Linux administrator username (default: lents)",
    )
    parser.add_argument(
        "--ssh-key",
        dest="ssh_authorized_key",
        required=True,
        help="Single-line SSH public key.",
    )
    parser.add_argument(
        "--tailscale",
        dest="tailscale_auth_key",
        help="Install and enrol Tailscale with this auth key.",
    )
    parser.add_argument(
        "--t3code",
        dest="with_t3code",
        action="store_true",
        help="Install T3 Code and the Codex CLI for the administrator.",
    )
    parser.add_argument(
        "--cyber",
        dest="with_cyber",
        action="store_true",
        help="Install reverse-engineering, exploit-development, and emulation tools.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Rendered cloud-init path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not USERNAME_PATTERN.fullmatch(args.admin_user):
        raise ValueError("ADMIN_USER must be a valid Linux username.")
    if not args.ssh_authorized_key:
        raise ValueError("--ssh-key must not be empty.")
    if "\n" in args.ssh_authorized_key or "\r" in args.ssh_authorized_key:
        raise ValueError("--ssh-key must be a single-line public key.")


def optional_write_files(args: argparse.Namespace) -> str:
    if not args.tailscale_auth_key:
        return ""
    return (
        f"  - path: /run/cloud-init/tailscale-auth-key\n"
        "    owner: root:root\n"
        "    permissions: '0600'\n"
        "    encoding: b64\n"
        f"    content: {base64_encode(args.tailscale_auth_key)}\n"
    )


def optional_bootstrap(args: argparse.Namespace) -> str:
    sections: list[str] = []
    if args.with_cyber:
        sections.append(
            "      apt-get install -y --no-install-recommends \\\n"
            "        binutils binwalk gdb openjdk-25-jdk patchelf \\\n"
            "        pipx python3-venv qemu-system qemu-user qemu-utils \\\n"
            "        ruby-full sagemath\n"
            "\n"
            "      install -d -o \"$admin_user\" -g \"$admin_user\" \"$admin_home/ctf\"\n"
            "\n"
            "      # Keep both GDB extensions available without having them overwrite ~/.gdbinit.\n"
            "      install -d -o \"$admin_user\" -g \"$admin_user\" \"$admin_home/.local/share\"\n"
            "      sudo -u \"$admin_user\" -H git clone --depth 1 https://github.com/pwndbg/pwndbg.git \\\n"
            "        \"$admin_home/.local/share/pwndbg\"\n"
            "      sudo -u \"$admin_user\" -H bash -lc 'cd \"$HOME/.local/share/pwndbg\" && ./setup.sh'\n"
            "      touch \"$admin_home/.gdbinit\"\n"
            "      sed -i '\\|pwndbg/gdbinit.py|d' \"$admin_home/.gdbinit\"\n"
            "      install -d -o \"$admin_user\" -g \"$admin_user\" \"$admin_home/.local/share/gef\"\n"
            "      curl -fsSL https://gef.blah.cat/py -o \"$admin_home/.local/share/gef/gef.py\"\n"
            "      chown \"$admin_user:$admin_user\" \"$admin_home/.local/share/gef/gef.py\"\n"
            "      printf '%s\\n' '#!/usr/bin/env bash' \\\n"
            "        'exec gdb -q -ex \"source $HOME/.local/share/pwndbg/gdbinit.py\" \"$@\"' \\\n"
            "        > /usr/local/bin/gdb-pwndbg\n"
            "      printf '%s\\n' '#!/usr/bin/env bash' \\\n"
            "        'exec gdb -q -ex \"source $HOME/.local/share/gef/gef.py\" \"$@\"' \\\n"
            "        > /usr/local/bin/gdb-gef\n"
            "      chmod 0755 /usr/local/bin/gdb-pwndbg /usr/local/bin/gdb-gef\n"
            "      sudo -u \"$admin_user\" -H pipx install ropper\n"
            "      gem install one_gadget\n"
            "      printf '%s\\n' 'export PATH=\"$HOME/.local/bin:$PATH\"' \\\n"
            "        > /etc/profile.d/cyber-tools.sh\n"
            "\n"
            "      # Install the current official Ghidra distribution and run its bundled server.\n"
            "      # The service uses a dedicated no-login account and persistent repositories.\n"
            "      ghidra_url=\"$(curl -fsSL https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest | \\\n"
            "        python3 -c 'import json, sys; release = json.load(sys.stdin); print(next(asset[\"browser_download_url\"] for asset in release[\"assets\"] if asset[\"name\"].endswith(\".zip\") and \"PUBLIC\" in asset[\"name\"]))')\"\n"
            "      install -d /opt/ghidra /var/lib/ghidra/repositories\n"
            "      curl -fsSL \"$ghidra_url\" -o /tmp/ghidra.zip\n"
            "      unzip -q /tmp/ghidra.zip -d /opt/ghidra\n"
            "      rm -f /tmp/ghidra.zip\n"
            "      ghidra_dir=\"$(find /opt/ghidra -mindepth 1 -maxdepth 1 -type d -name 'ghidra_*' -print -quit)\"\n"
            "      test -n \"$ghidra_dir\"\n"
            "      ln -sfn \"$ghidra_dir\" /opt/ghidra/current\n"
            "      useradd --system --home /var/lib/ghidra --shell /usr/sbin/nologin ghidra\n"
            "      java_home=\"$(dirname \"$(dirname \"$(readlink -f \"$(command -v java)\")\")\")\"\n"
            "      sed -i \\\n"
            "        -e 's|^ghidra.repositories.dir=.*|ghidra.repositories.dir=/var/lib/ghidra/repositories|' \\\n"
            "        -e 's|^#wrapper.app.account=.*|wrapper.app.account=ghidra|' \\\n"
            "        -e \"s|^# GHIDRA_JAVA_HOME=.*|GHIDRA_JAVA_HOME=$java_home|\" \\\n"
            "        \"$ghidra_dir/server/server.conf\" \"$ghidra_dir/server/ghidraSvr\"\n"
            "      chown -R ghidra:ghidra /opt/ghidra /var/lib/ghidra\n"
            "      \"$ghidra_dir/server/svrInstall\"\n"
            "      printf '%s\\n' '#!/usr/bin/env bash' 'exec /opt/ghidra/current/server/svrAdmin -add \"$1\" --p' \\\n"
            "        > /usr/local/sbin/ghidra-add-user\n"
            "      chmod 0755 /usr/local/sbin/ghidra-add-user\n"
        )
    if args.with_t3code:
        sections.append(
            "      npm install --global @openai/codex t3@latest\n"
            "      # Authenticate interactively after provisioning with: codex login\n"
            "      # Then start T3 Code with: t3\n"
        )
    if args.tailscale_auth_key:
        sections.append(
            "      curl -fsSL https://tailscale.com/install.sh | sh\n"
            "      tailscale_auth_key=\"$(base64 -d /run/cloud-init/tailscale-auth-key)\"\n"
            "      tailscale up --auth-key=\"$tailscale_auth_key\"\n"
            "      rm -f /run/cloud-init/tailscale-auth-key\n"
        )
    return "\n".join(sections)


def render(args: argparse.Namespace) -> str:
    template = DEFAULT_TEMPLATE.read_text()
    replacements = {
        "__ADMIN_USER__": args.admin_user,
        "__SSH_KEY_B64__": base64_encode(args.ssh_authorized_key),
        "__TMUX_CONFIG_B64__": base64_encode(
            (REPO_ROOT / "dotfiles" / "tmux.conf").read_bytes()
        ),
        "__OPTIONAL_WRITE_FILES__": optional_write_files(args),
        "__OPTIONAL_BOOTSTRAP__": optional_bootstrap(args),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    args.output.write_text(render(args))
    print(f"Rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
