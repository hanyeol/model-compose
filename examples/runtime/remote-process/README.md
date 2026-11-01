# Remote Process Runtime (shell on an SSH host)

Runs the `shell` component inside a worker **process on a remote host**
reached over SSH. The controller stays on your local machine; the worker
is `python -m mindor.core.component.runtime.process` launched by the
controller on the remote side, and the shell command executes in the
worker's local shell on that host.

Use this example to validate the `process + remote` runtime end-to-end
with a dependency-free workload. Once this works, swap the `shell`
component for anything else that uses `runtime: process` — the remote
wiring is the same.

## Prerequisites

Required on the remote host:

- SSH access via key authentication.
- A Python interpreter that can `import mindor`. The simplest path is
  installing this project (`pip install -e .` from a clone, or
  `pip install model-compose` when a release is available) in a system
  or user site-packages that the login shell's `python` can see.
- A `python` executable on the remote user's `$PATH`.

No daemons, no containers, no volume mounts — just SSH and Python.

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

`REMOTE_WORKING_DIR` is the directory the worker ``cd``s into before
launching Python. Point it at the remote clone / install location of
mindor so `import mindor` resolves correctly.

The key must be unencrypted or available via the local SSH agent; agent
fallback and encrypted keys are not supported yet.

## Try it

```bash
model-compose up
model-compose run --input '{}'
```

Expected output: a line like

```
hello from <remote-hostname>: Linux <remote-hostname> 6.x.x-generic ... x86_64 GNU/Linux
```

The `hostname` and `uname -a` are evaluated **on the remote host**, so a
mismatch with your local machine confirms the worker is running there.

What `model-compose up` does:

1. Opens an SSH connection to `REMOTE_HOST` as `REMOTE_USER`.
2. Starts `python -m mindor.core.component.runtime.process` on the
   remote side, with the exec channel's stdin/stdout carrying the IPC
   stream (framed messages) and stderr carrying log output.
3. Sends the component config over IPC as a START message. The remote
   worker brings up the `shell` component in-process.

When you then `model-compose run`:

- The input is forwarded over the SSH exec channel, the shell command
  runs on the remote host, and the stdout is returned.

`model-compose down` closes the SSH connection; the worker process on
the remote side exits with it.

## Why this example

`shell` has no model weights, no GPU, no pip install — it isolates the
remote-process plumbing from everything else. If this round-trip works,
the SSH transport, exec channel, and worker handshake are all healthy;
any failure in a heavier `process + remote` workload is in the
workload, not the runtime.
