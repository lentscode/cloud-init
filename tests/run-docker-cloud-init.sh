#!/usr/bin/env bash
# Provision the base cloud-init profile in a disposable Ubuntu container.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image_name="personal-cloud-init-test"
container_name="personal-cloud-init-test-$$"
seed_dir="$(mktemp -d)"
ssh_key="${SSH_KEY:-ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockKeyForDockerCloudInitTestOnly docker-cloud-init-test}"

cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  rm -rf "$seed_dir"
}
trap cleanup EXIT

command -v docker >/dev/null || {
  echo 'Docker is required to run this integration test.' >&2
  exit 1
}

python3 "$repo_root/scripts/render_user_data.py" \
  --ssh-key "$ssh_key" \
  --output "$seed_dir/user-data"
printf 'instance-id: docker-cloud-init-test\nlocal-hostname: cloud-init-test\n' > "$seed_dir/meta-data"

docker build --tag "$image_name" --file "$repo_root/tests/Dockerfile" "$repo_root"
docker run --detach --name "$container_name" \
  --privileged --cgroupns=host \
  --volume /sys/fs/cgroup:/sys/fs/cgroup:rw \
  --volume "$seed_dir:/var/lib/cloud/seed/nocloud:ro" \
  "$image_name" >/dev/null

if ! docker exec "$container_name" cloud-init status --wait; then
  docker logs "$container_name" >&2 || true
  docker exec "$container_name" tail -200 /var/log/cloud-init-output.log >&2 || true
  exit 1
fi
docker exec "$container_name" bash -ceu '
  test "$(getent passwd lents | cut -d: -f7)" = /bin/zsh
  id lents | grep -qw sudo
  test -f /home/lents/.tmux.conf
  test -x /usr/local/bin/nvim
  test -d /home/lents/.config/nvim/.git
  test -f /home/lents/.zshrc
  grep -Fqx "export PNPM_HOME=\"\$HOME/.local/share/pnpm\"" /home/lents/.zshrc
  sudo -l -U lents | grep -Fq "(ALL) NOPASSWD: ALL"
'

echo 'Docker cloud-init integration test passed.'
