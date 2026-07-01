"""Unit tests for the docker worker entrypoint.

After moving IPC to docker attach (stdin/stdout), the entrypoint is driven
by `IpcStdioChannel`:

- `IpcStdioChannel.setup()` — dup fd 0/1, redirect to fd 2 (stderr), so that
  any `print(...)` from user code goes to `docker logs` rather than
  corrupting the IPC stream. Hard to unit-test in-process without colliding
  with pytest's stdio capture, so we cover it separately via subprocess
  (see `test_setup_subprocess`).
- `IpcStdioChannel.run(worker_class)` — INIT handshake + worker run loop,
  parametrized by the worker class. Trivial to test in-process by injecting
  `os.pipe()` ends as `ipc_in` / `ipc_out`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from mindor.core.component.runtime.base.ipc_stdio_channel import IpcStdioChannel
from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
from mindor.core.component.runtime.docker import ComponentDockerRuntimeWorker


# ---------------------------------------------------------------------------
# IpcStdioChannel.run — INIT handshake error paths.
# ---------------------------------------------------------------------------

class TestIpcStdioChannelHandshake:
    def _make_channel(self, ipc_in, ipc_out) -> IpcStdioChannel:
        channel = IpcStdioChannel()
        channel.ipc_in = ipc_in
        channel.ipc_out = ipc_out
        return channel

    def test_eof_before_init_raises(self):
        r, w = os.pipe()
        os.close(w)  # immediate EOF on read side
        ipc_in = os.fdopen(r, "rb", buffering=0)
        # ipc_out is irrelevant since we fail before any write.
        out_r, out_w = os.pipe()
        ipc_out = os.fdopen(out_w, "wb", buffering=0)
        try:
            channel = self._make_channel(ipc_in, ipc_out)
            with pytest.raises(RuntimeError, match="Expected IPC message, got EOF"):
                channel.run(ComponentDockerRuntimeWorker)
        finally:
            ipc_in.close(); ipc_out.close(); os.close(out_r)

    def test_first_message_not_start_raises(self):
        r, w = os.pipe()
        wrong = IpcMessage(type=IpcMessageType.RUN, request_id="r1", payload={})
        os.write(w, wrong.serialize() + b"\n")
        os.close(w)
        ipc_in = os.fdopen(r, "rb", buffering=0)
        out_r, out_w = os.pipe()
        ipc_out = os.fdopen(out_w, "wb", buffering=0)
        try:
            channel = self._make_channel(ipc_in, ipc_out)
            with pytest.raises(RuntimeError, match="Expected first IPC message of type 'start'"):
                channel.run(ComponentDockerRuntimeWorker)
        finally:
            ipc_in.close(); ipc_out.close(); os.close(out_r)

    def test_run_without_setup_raises(self):
        channel = IpcStdioChannel()
        with pytest.raises(RuntimeError, match="setup"):
            channel.run(ComponentDockerRuntimeWorker)


# ---------------------------------------------------------------------------
# IpcStdioChannel.setup — verified via subprocess so pytest's stdio capture
# is out of the way.
# ---------------------------------------------------------------------------

_FD_PROBE_SCRIPT = textwrap.dedent("""
    import os, sys, struct
    # Make this script importable from the source tree the parent uses.
    sys.path.insert(0, %(src)r)
    from mindor.core.component.runtime.base.ipc_stdio_channel import IpcStdioChannel
    channel = IpcStdioChannel()
    channel.setup()
    ipc_in, ipc_out = channel.ipc_in, channel.ipc_out
    # Write a known marker to the original stdout via the IPC handle.
    ipc_out.write(b"IPC_OK\\n")
    ipc_out.flush()
    # Now do user-code-style writes to stdout — they must NOT reach the IPC pipe.
    print("USER_STDOUT_LINE", flush=True)
    sys.stdout.write("USER_DIRECT_WRITE\\n"); sys.stdout.flush()
    # And read whatever the parent put on stdin via the IPC in handle.
    line = ipc_in.readline()
    ipc_out.write(b"GOT:" + line)
    ipc_out.flush()
""")


def _src_root() -> str:
    """Path to the source tree to inject onto the subprocess's sys.path."""
    import mindor
    return os.path.dirname(os.path.dirname(os.path.abspath(mindor.__file__)))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fd semantics")
def test_setup_subprocess(tmp_path):
    """In a clean subprocess, verify the fd dance:
    - bytes written via ipc_out appear on the child's real stdout
    - bytes written via print(...) / sys.stdout appear on the child's stderr
    - bytes the parent puts on stdin are readable via ipc_in
    """
    script = tmp_path / "probe.py"
    script.write_text(_FD_PROBE_SCRIPT % {"src": _src_root()})

    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    out, err = proc.communicate(input=b"parent-to-child\n", timeout=10)

    # IPC stream (real stdout) carries:
    #   1. the IPC_OK marker, and
    #   2. the GOT: echo of the parent's stdin line.
    # It must NOT carry the user's print/write output.
    assert b"IPC_OK\n" in out
    assert b"GOT:parent-to-child\n" in out
    assert b"USER_STDOUT_LINE" not in out
    assert b"USER_DIRECT_WRITE" not in out

    # stderr carries the user output (where `docker logs` would find it).
    assert b"USER_STDOUT_LINE" in err
    assert b"USER_DIRECT_WRITE" in err
