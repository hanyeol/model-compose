# Remote VirtualEnv Runtime (shell inside a remote venv)

Runs the `shell` component inside a **venv-isolated worker on a remote
host** reached over SSH. The controller stays on your local machine; the
venv is created on the remote filesystem under the SSH user's
``working_dir`` and the worker is `python -m
mindor.core.component.runtime.virtualenv.remote` run from inside that
venv.

Use this example to validate the `virtualenv + remote` runtime
end-to-end. The venv provisioning is lazy — the first `up` creates it
and installs `mindor` + its runtime requirements; subsequent runs reuse
the same venv in seconds.

## Prerequisites

Required on the remote host:

- SSH access via key authentication.
- A Python interpreter that can `import mindor` under the user's
  interactive shell (pyenv, system python, or an activated venv in
  `.bashrc` all work). The runtime resolves it via `sys.executable`.
- `python -m venv` available (standard library — no extra install).
- Optional: `uv` on `$PATH` makes requirement installation dramatically
  faster, with wheel caching across venvs. The runtime falls back to
  the venv's `pip` when `uv` is not found.

The remote mindor is wired via a `mindor.pth` file in the venv's
site-packages (editable-install style), so no byte transfer happens
between host and remote during setup.

## Setup

Copy `.env.sample` to `.env` and fill in your SSH details:

```bash
cp .env.sample .env
```

```bash
REMOTE_HOST=gpu-box.example.com
REMOTE_USER=hanyeol
REMOTE_SSH_KEY=~/.ssh/id_ed25519
REMOTE_WORKING_DIR=/home/hanyeol/Projects/model-compose
```

`REMOTE_WORKING_DIR` is both:
- The directory the SSH session `cd`s into before resolving python / mindor.
- The anchor for the venv path (`{working_dir}/.runtime/components/<id>/venv`).

Point it at the remote clone / install location of mindor so `import
mindor` resolves correctly.

## Try it

```bash
model-compose up
model-compose run --input '{}'
```

Expected output: a line like

```
hello from <remote-hostname>: Linux <remote-hostname> ... x86_64 GNU/Linux via /home/.../.runtime/components/__component__/venv/bin/python
```

The `hostname`, `uname -a`, and `sys.executable` are all evaluated **on
the remote host**, and the python path reports the **venv's** interpreter
— confirming the shell command ran inside the venv.

What `model-compose up` does on first launch:

1. Opens an SSH connection to `REMOTE_HOST` as `REMOTE_USER`.
2. Resolves the remote user's python (interactive-shell `sys.executable`)
   and the directory that owns `import mindor`.
3. Creates `{REMOTE_WORKING_DIR}/.runtime/components/__component__/venv`
   via `<remote-python> -m venv ...` (skipped if it already exists).
4. Writes `mindor.pth` into the venv's site-packages pointing at the
   remote mindor source.
5. Runs `uv pip install` (or venv pip) for the mindor runtime
   requirements. Second launch skips 3–5 entirely.
6. Launches `python -m mindor.core.component.runtime.virtualenv.remote`
   from the venv over the exec channel. Stdio carries the IPC stream.

When you then `model-compose run`:

- The input is forwarded over the SSH exec channel, the shell command
  runs on the remote host inside the venv, and the stdout is returned.

`model-compose down` closes the SSH connection; the worker exits with
it. The venv on disk survives for the next `up`.

## Why this example

`shell` has no model weights, no GPU, no project-specific requirements —
it isolates the remote-venv plumbing from everything else. If this
round-trip works, the SSH transport, venv provisioning, mindor source
wiring, and worker handshake are all healthy; any failure in a heavier
`virtualenv + remote` workload is in the workload, not the runtime.
