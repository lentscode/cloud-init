# Personal Ubuntu cloud-init

This repository produces a `cloud-init` user-data file for a personal Ubuntu
VM. It creates an SSH-only administrator, installs a development environment,
sets up Neovim and tmux, and can optionally enrol the machine in Tailscale.

## What it installs

- Build tooling: `build-essential`, Git, curl, unzip, xz, and pkg-config
- Go (`golang-go` from Ubuntu)
- Node.js LTS and pnpm (NodeSource LTS + Corepack)
- Rust via rustup, for the VM administrator
- Neovim from the official latest stable Linux archive
- Tailscale from Tailscale's official install script
- Your Neovim configuration from `https://github.com/lentscode/nvim-config`
- The tmux configuration tracked in this repository

## Render user-data

The renderer deliberately requires an SSH public key and accepts the
Tailscale key only as an environment variable. Neither belongs in Git.

```sh
SSH_AUTHORIZED_KEY="$(<~/.ssh/id_ed25519.pub)" \
TAILSCALE_AUTH_KEY="tskey-auth-..." \
./scripts/render-user-data.sh
```

This writes `user-data.yaml`, which is ignored by Git. Upload that file to
your VM provider as cloud-init user data. Omit `TAILSCALE_AUTH_KEY` when you
do not want to enrol the VM; you can render a new file with a fresh ephemeral
key for every instance.

The default administrator is `lents`. Override it when rendering if needed:

```sh
ADMIN_USER=myname SSH_AUTHORIZED_KEY="$(<~/.ssh/id_ed25519.pub)" ./scripts/render-user-data.sh
```

After cloud-init completes, connect with `ssh lents@VM_IP`. Check progress on
the VM with `cloud-init status --wait` and `/var/log/cloud-init-output.log`.

## Optional Ubuntu packages

Tell me which of these you want and they can be added to the base profile:

- CLI: `zsh`, `bat`, `fd-find`, `tree`, `htop`, `btop`, `direnv`, `shellcheck`
- Python: `python3-venv`, `pipx`, `uv`
- Containers: `docker.io`, Docker Compose plugin, `podman`
- Databases and clients: `postgresql-client`, `redis-tools`, `sqlite3`
- Infrastructure: `terraform`, `ansible`, `kubectl`, `helm`
- Build and language tooling: `cmake`, `ninja-build`, `clang`, `protobuf-compiler`, `just`

## Updating tmux

Edit `dotfiles/tmux.conf` here, then render a fresh user-data file. The
template embeds the tracked file into the VM at provision time.

