# Personal Ubuntu cloud-init

This repository produces a `cloud-init` user-data file for a personal Ubuntu
VM. It creates an SSH-only administrator, installs a development environment,
sets up Neovim and tmux, and can optionally enrol the machine in Tailscale or
install T3 Code or a reverse-engineering toolchain.

## What it installs

- Build tooling: `build-essential`, `cloc`, `fzf`, Git, curl, unzip, xz, and pkg-config
- Go (`golang-go` from Ubuntu)
- Zsh as the administrator's login shell, with Oh My Zsh (installed using its
  official unattended installer) and the `agnoster` theme
- Node.js LTS (NodeSource) and pnpm (its official standalone installer)
- Docker Engine, Buildx, and Docker Compose from Docker's official apt repository;
  the administrator is added to the `docker` group, so Docker can be used without
  `sudo` after reconnecting
- Rust via rustup, for the VM administrator
- Zsh `PATH` entries for user-installed tools: `~/.local/bin`, pnpm, and Cargo
- Neovim from the official latest stable Linux archive
- A `vim` alias that opens Neovim
- Your Neovim configuration from `https://github.com/lentscode/nvim-config`
- The tmux configuration tracked in this repository
- Sesh v2.32.0, zoxide, and `fd-find`, with your shared `s` session picker
- Tmuxinator from Ubuntu's package repository, including its Ruby dependencies

## Render user-data

The Python renderer deliberately requires an SSH public key argument. Optional
features are omitted unless their argument or flag is present, so the generated
file contains only the selected configuration. Secrets do not belong in Git.

```sh
./scripts/render_user_data.py \
  --ssh-key "$(<~/.ssh/id_ed25519.pub)" \
  --tailscale "tskey-auth-..." \
  --t3code \
  --cyber
```

This writes `user-data.yaml`, which is ignored by Git. Upload that file to
your VM provider as cloud-init user data. Use any combination of the feature
flags below:

- `--tailscale` installs and enrols Tailscale. Omit it to leave
  Tailscale out. Render a new file with a fresh ephemeral key for every
  instance.
- `--t3code` installs the Codex CLI using OpenAI's Linux installer and adds a
  `t3` launcher that runs T3 Code through its official `npx` method. After
  connecting to the VM, authenticate with `codex login` and launch T3 Code
  with `t3`.
- `--cyber` installs Ghidra, pwndbg, GEF, ropper, one_gadget, patchelf,
  binutils, binwalk, and QEMU. It installs the current official Ghidra release
  as a service using the `ghidra` account, with repositories at
  `/var/lib/ghidra/repositories` and private-password authentication enabled.
  It also creates `/home/<admin-user>/ctf` as the workspace for competitions.
  Use `ghidra`, `pwndbg`, or `gef` directly from your shell; the latter two start
  GDB with the corresponding extension. Ghidra Server listens on its default port
  (`13100`); restrict network access at the VM provider or firewall before exposing
  it beyond trusted users. Add the first server user
  after connecting with `sudo ghidra-add-user <username>`; it securely prompts
  for that user's initial password.
  Ropper is installed in an isolated `pipx` environment using the compatible
  pure-Python `filebytes` wheel, which also supports Ubuntu 26.04's Python 3.14.

For the base profile only:

```sh
./scripts/render_user_data.py --ssh-key "$(<~/.ssh/id_ed25519.pub)"
```

The default administrator is `lents`. Override it when rendering if needed:

```sh
./scripts/render_user_data.py \
  --admin-user myname \
  --ssh-key "$(<~/.ssh/id_ed25519.pub)"
```

After cloud-init completes, connect with `ssh lents@VM_IP`. Check progress on
the VM with `cloud-init status --wait` and `/var/log/cloud-init-output.log`.

## Optional Ubuntu packages

Tell me which of these you want and they can be added to the base profile:

- CLI: `zsh`, `bat`, `fd-find`, `tree`, `htop`, `btop`, `direnv`, `shellcheck`
- Python: `python3-venv`, `pipx`, `uv`
- Containers: `podman`
- Databases and clients: `postgresql-client`, `redis-tools`, `sqlite3`
- Infrastructure: `terraform`, `ansible`, `kubectl`, `helm`
- Build and language tooling: `cmake`, `ninja-build`, `clang`, `protobuf-compiler`, `just`

## Updating tmux

Edit `dotfiles/tmux.conf` here, then render a fresh user-data file. The
template embeds the tracked file into the VM at provision time.

The renderer also embeds `dotfiles/s` as `~/.local/bin/s` and
`dotfiles/sesh.toml` as `~/.config/sesh/sesh.toml`. Interactive SSH logins
outside tmux open this picker; inside tmux, press the prefix, then `Shift+T`
to open it in a popup. With the default prefix, that is `Ctrl+B`, then `Shift+T`.
Cancelling with Escape or `Ctrl+D` returns to the shell without closing SSH.
SSH commands such as `ssh VM_IP uptime` skip the picker.

Select Home on a fresh VM to create your first session. Later, directory visits
recorded by zoxide appear in the picker too. You can also run `s ~/my-project`
to connect directly to a project directory. The picker keeps your local filters
and preview: `Ctrl+A` for all entries, `Ctrl+T` for tmux, `Ctrl+G` for configured
sessions, `Ctrl+X` for zoxide, and `Ctrl+F` to search directories under home.
The search uses Ubuntu's `fdfind` command instead of macOS's `fd`.

Sesh is installed through its [official Go installation method](https://github.com/joshmedeski/sesh#how-to-install),
with a pinned version so provisioning does not silently switch releases.
Go downloads a newer toolchain if that version requires it. The executable goes
in `/usr/local/bin`, making it available to tmux as well as interactive Zsh.
Zoxide records directory visits without changing the usual `cd` command.

To create a reusable tmux layout, run `EDITOR=nvim tmuxinator new dev` on the VM
and edit the generated project file. For example, define separate windows for
your editor, server, and logs, then open that layout with `tmuxinator start dev`.

Each invocation of the renderer chooses one status-bar background from a
contrast-checked palette and embeds it in that cloud-init file. Its foreground
stays white for readable text; the palette is deliberately kept distinct from
both light and dark terminal backgrounds. Reloading tmux does not change the
color; render a new user-data file to choose a new one.

## Docker integration test

The base profile can be provisioned in a disposable Ubuntu container using
cloud-init's NoCloud datasource. This is an integration test for the rendered
configuration, rather than a replacement for a final VM-provider test.

```sh
chmod +x tests/run-docker-cloud-init.sh
./tests/run-docker-cloud-init.sh
```

It builds `tests/Dockerfile`, renders a fresh user-data file into a temporary
NoCloud seed, boots systemd and cloud-init, and verifies the administrator,
tmux binding, sesh installation and Home entry, tmuxinator, picker permissions, Neovim,
Neovim configuration, Zsh configuration, and sudo policy.
It requires a Linux Docker host because systemd is run with a privileged
container and a cgroup mount. The default test does not enable Tailscale,
T3 Code, or the cyber toolchain: those options require external credentials or
substantially longer, network-dependent provisioning.
