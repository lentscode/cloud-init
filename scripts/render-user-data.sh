#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
template="$repo_root/templates/user-data.yaml.tmpl"
output="$repo_root/user-data.yaml"

: "${SSH_AUTHORIZED_KEY:?Set SSH_AUTHORIZED_KEY to the contents of your public key.}"
admin_user="${ADMIN_USER:-lents}"
tailscale_auth_key="${TAILSCALE_AUTH_KEY:-}"

if [[ ! "$admin_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "ADMIN_USER must be a valid Linux username." >&2
  exit 1
fi

if [[ "$SSH_AUTHORIZED_KEY" == *$'\n'* ]]; then
  echo "SSH_AUTHORIZED_KEY must be a single-line public key." >&2
  exit 1
fi

base64_no_wrap() {
  printf %s "$1" | base64 | tr -d '\n'
}

ssh_key_b64="$(base64_no_wrap "$SSH_AUTHORIZED_KEY")"
if [[ -n "$tailscale_auth_key" ]]; then
  tailscale_key_b64="$(base64_no_wrap "$tailscale_auth_key")"
else
  tailscale_key_b64="$(base64_no_wrap 'tailscale-not-configured')"
fi
tmux_config_b64="$(base64 < "$repo_root/dotfiles/tmux.conf" | tr -d '\n')"

sed \
  -e "s|__ADMIN_USER__|$admin_user|g" \
  -e "s|__SSH_KEY_B64__|$ssh_key_b64|g" \
  -e "s|__TAILSCALE_KEY_B64__|$tailscale_key_b64|g" \
  -e "s|__TMUX_CONFIG_B64__|$tmux_config_b64|g" \
  "$template" > "$output"

echo "Rendered $output"
