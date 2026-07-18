"""Unit tests for ``StdoutRelay``.

``StdoutRelay`` reserves process fd 1 for the caller and redirects incidental
writes to fd 2 for the duration of the context. Uses pytest's ``capfd`` which
captures at the fd level and cooperates with our fd manipulation.
"""

from __future__ import annotations

import os
import sys

import anyio
import pytest

from mindor.core.utils.transport.stdout_relay import StdoutRelay


class TestStdoutRelay:
    def test_yields_stream_writing_to_original_stdout(self, capfd):
        async def _run():
            with StdoutRelay() as raw_stdout:
                await raw_stdout.write("mcp-frame\n")
                await raw_stdout.flush()

        anyio.run(_run)

        out, err = capfd.readouterr()
        assert out == "mcp-frame\n"
        assert err == ""

    def test_prints_inside_context_go_to_stderr(self, capfd):
        with StdoutRelay():
            print("stray output", flush=True)

        out, err = capfd.readouterr()
        assert out == ""
        assert "stray output" in err

    def test_fd_1_writes_inside_context_go_to_stderr(self, capfd):
        with StdoutRelay():
            os.write(1, b"third-party-fd1\n")

        out, err = capfd.readouterr()
        assert out == ""
        assert "third-party-fd1" in err

    def test_restores_sys_stdout_on_exit(self):
        before = sys.stdout
        with StdoutRelay():
            assert sys.stdout is sys.stderr
        assert sys.stdout is before
