"""Tests for `AppleContainerClient` — the thin async wrapper around the
Apple Container `container` CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.utils.containers.apple_container_client import AppleContainerClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _stub_container_cli_present():
    """Pretend the `container` CLI is installed so the client's __init__
    preflight check passes on any host running the test suite."""
    with patch(
        "mindor.core.utils.containers.apple_container_client.shutil.which",
        return_value="/usr/local/bin/container",
    ):
        yield


def _mock_process(returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(b"", stderr))
    return process


@pytest.mark.anyio
class TestAppleContainerClientInvocation:
    """`container` argv assembly: command (str | List[str]) + args + the
    fixed `container` prefix."""

    async def test_string_command_no_args(self):
        process = _mock_process()
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as mock_exec:
            client = AppleContainerClient()
            await client.run("ls")

            args, _ = mock_exec.call_args
            assert args == ("container", "ls")

    async def test_string_command_with_args(self):
        process = _mock_process()
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as mock_exec:
            client = AppleContainerClient()
            await client.run("stop", args=["my-container"])

            args, _ = mock_exec.call_args
            assert args == ("container", "stop", "my-container")

    async def test_list_command(self):
        process = _mock_process()
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as mock_exec:
            client = AppleContainerClient()
            await client.run(["image", "ls"])

            args, _ = mock_exec.call_args
            assert args == ("container", "image", "ls")

    async def test_list_command_with_args(self):
        process = _mock_process()
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as mock_exec:
            client = AppleContainerClient()
            await client.run(["system", "dns", "create"], args=["test.local"])

            args, _ = mock_exec.call_args
            assert args == ("container", "system", "dns", "create", "test.local")


@pytest.mark.anyio
class TestAppleContainerClientErrorHandling:
    """`raise_on_error` controls whether non-zero exits become RuntimeErrors."""

    async def test_zero_exit_succeeds(self):
        process = _mock_process(returncode=0)
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            client = AppleContainerClient()
            await client.run("ls")  # must not raise

    async def test_nonzero_exit_raises_when_raise_on_error_true(self):
        process = _mock_process(returncode=1, stderr=b"container not found")
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            client = AppleContainerClient()
            with pytest.raises(RuntimeError, match="failed"):
                await client.run("stop", args=["ghost"])

    async def test_nonzero_exit_does_not_raise_when_raise_on_error_false(self):
        process = _mock_process(returncode=1, stderr=b"oops")
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            client = AppleContainerClient()
            result = await client.run("ls", raise_on_error=False)
            assert result is process

    async def test_error_message_includes_stderr(self):
        process = _mock_process(returncode=2, stderr=b"detailed reason")
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            client = AppleContainerClient()
            with pytest.raises(RuntimeError, match="detailed reason"):
                await client.run("stop", args=["x"])


@pytest.mark.anyio
class TestAppleContainerClientCaptureOutput:
    """`capture_output` toggles PIPE vs inherited stdio."""

    async def test_capture_output_true_uses_pipe(self):
        process = _mock_process()
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as mock_exec:
            client = AppleContainerClient()
            await client.run("ls", capture_output=True)

            import asyncio as _asyncio
            kwargs = mock_exec.call_args.kwargs
            assert kwargs["stdout"] == _asyncio.subprocess.PIPE
            assert kwargs["stderr"] == _asyncio.subprocess.PIPE

    async def test_capture_output_false_inherits_stdio(self):
        process = _mock_process()
        with patch(
            "mindor.core.utils.containers.apple_container_client.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as mock_exec:
            client = AppleContainerClient()
            await client.run("run", args=["my-image"], capture_output=False)

            import sys as _sys
            kwargs = mock_exec.call_args.kwargs
            assert kwargs["stdout"] is _sys.stdout
            assert kwargs["stderr"] is _sys.stderr


class TestAppleContainerClientPreflight:
    """`__init__` verifies the `container` CLI is on PATH before doing anything."""

    def test_missing_cli_raises(self):
        with patch(
            "mindor.core.utils.containers.apple_container_client.shutil.which",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="Apple Container CLI"):
                AppleContainerClient()

    def test_present_cli_succeeds(self):
        with patch(
            "mindor.core.utils.containers.apple_container_client.shutil.which",
            return_value="/opt/homebrew/bin/container",
        ):
            client = AppleContainerClient()
            assert client.verbose is False
