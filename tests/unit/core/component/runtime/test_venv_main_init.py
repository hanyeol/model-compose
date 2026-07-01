"""Unit tests for the venv worker `main()` INIT handshake.

`mindor.core.component.runtime.virtualenv.main` is the entrypoint that the
parent launches via `python -m mindor.core.component.runtime.virtualenv`.
Before the IPC dispatch loop starts, it must:

1. Read the IPC fd pair from `MINDOR_VENV_REQUEST_FD` /
   `MINDOR_VENV_RESPONSE_FD` environment variables.
2. Receive the very first message (which must be `IpcMessageType.START`)
   and validate it as the INIT payload.

These tests cover the failure paths around that handshake — the happy
path requires constructing a real component instance, which is exercised
elsewhere by the end-to-end venv runtime integration tests.

We feed the channel via the same fd-pair construction the production
code uses, so the actual `SubprocessPipeChannel` is exercised — only the
`asyncio.run(worker.run())` tail is what we avoid by inducing an early
RuntimeError.
"""

from __future__ import annotations

import os
from typing import Tuple

import pytest

from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
from mindor.core.component.runtime.virtualenv import main as venv_main
from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel


def _make_fd_pair() -> Tuple[int, int, int, int]:
    """Return (request_r, request_w, response_r, response_w).

    The child (main) will read from `request_r` and write to `response_w`.
    The test (acting as parent) writes to `request_w` and reads from `response_r`.
    """
    request_r, request_w = os.pipe()
    response_r, response_w = os.pipe()
    return request_r, request_w, response_r, response_w


def _close_all(*fds: int) -> None:
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


class TestVenvMainInit:
    def test_missing_request_fd_env_raises(self, monkeypatch):
        monkeypatch.delenv("MINDOR_VENV_REQUEST_FD", raising=False)
        monkeypatch.setenv("MINDOR_VENV_RESPONSE_FD", "99")

        with pytest.raises(RuntimeError, match="Missing IPC file descriptor"):
            venv_main()

    def test_missing_response_fd_env_raises(self, monkeypatch):
        monkeypatch.setenv("MINDOR_VENV_REQUEST_FD", "99")
        monkeypatch.delenv("MINDOR_VENV_RESPONSE_FD", raising=False)

        with pytest.raises(RuntimeError, match="Missing IPC file descriptor"):
            venv_main()

    def test_eof_before_init_raises(self, monkeypatch):
        """Parent closes the channel without sending START → child must
        raise the dedicated EOF RuntimeError, not blow up on JSON parsing."""
        request_r, request_w, response_r, response_w = _make_fd_pair()
        try:
            monkeypatch.setenv("MINDOR_VENV_REQUEST_FD", str(request_r))
            monkeypatch.setenv("MINDOR_VENV_RESPONSE_FD", str(response_w))

            # Close the parent side of request without sending → child sees EOF.
            os.close(request_w)
            request_w = -1

            with pytest.raises(RuntimeError, match="Expected first IPC message.*EOF"):
                venv_main()
        finally:
            # `main()` takes ownership of (request_r, response_w) via the
            # channel and closes them on the RuntimeError path (channel is
            # constructed before recv()). The other ends are still ours.
            _close_all(response_r)
            if request_w != -1:
                _close_all(request_w)

    def test_first_message_not_start_raises(self, monkeypatch):
        """Parent sends RUN as the first message instead of START → child
        must reject it with a clear message naming the actual type."""
        request_r, request_w, response_r, response_w = _make_fd_pair()
        # Parent's view of the channel: writes to request_w, reads response_r.
        parent = SubprocessPipeChannel(request_fd=response_r, response_fd=request_w)
        try:
            monkeypatch.setenv("MINDOR_VENV_REQUEST_FD", str(request_r))
            monkeypatch.setenv("MINDOR_VENV_RESPONSE_FD", str(response_w))

            wrong_first = IpcMessage(type=IpcMessageType.RUN, request_id="r1", payload={})
            parent.send(wrong_first.serialize())

            with pytest.raises(RuntimeError, match="Expected first IPC message of type 'start'"):
                venv_main()
        finally:
            parent.close()
