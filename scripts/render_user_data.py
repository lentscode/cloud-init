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
