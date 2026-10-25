"""Unit tests for ``ControllerService._close_task_output``.

When a streaming task is cancelled (``POST /tasks/{id}/cancel``), the controller
must close the output stream so the upstream — an HTTP response, a model still
generating — is released. Prior to the fix, the ``CancelledError`` handler
dropped ``output`` without closing it and the upstream kept running.
"""

from typing import Any, AsyncIterator, List

import pytest

from mindor.core.controller.base import ControllerService


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _AcloseOnlyOutput:
    def __init__(self) -> None:
        self.aclosed = 0

    async def aclose(self) -> None:
        self.aclosed += 1


class _CloseOnlyOutput:
    def __init__(self) -> None:
        self.closed = 0

    async def close(self) -> None:
        self.closed += 1


class _BothCloseOutput:
    """When both are present, ``aclose`` is preferred (iterator contract)."""

    def __init__(self) -> None:
        self.aclosed = 0
        self.closed = 0

    async def aclose(self) -> None:
        self.aclosed += 1

    async def close(self) -> None:
        self.closed += 1


class _NoCloseOutput:
    pass


class _RaisingAcloseOutput:
    def __init__(self) -> None:
        self.aclosed = 0

    async def aclose(self) -> None:
        self.aclosed += 1
        raise RuntimeError("close failed")


# Unbound: self is unused.
_close = ControllerService._close_task_output


@pytest.mark.anyio
async def test_aclose_is_called_on_iterator_shaped_output():
    output = _AcloseOnlyOutput()
    await _close(None, output)
    assert output.aclosed == 1


@pytest.mark.anyio
async def test_close_is_called_on_resource_shaped_output():
    output = _CloseOnlyOutput()
    await _close(None, output)
    assert output.closed == 1


@pytest.mark.anyio
async def test_aclose_wins_over_close_when_both_present():
    output = _BothCloseOutput()
    await _close(None, output)
    assert output.aclosed == 1
    assert output.closed == 0


@pytest.mark.anyio
async def test_output_without_close_methods_is_a_noop():
    await _close(None, _NoCloseOutput())


@pytest.mark.anyio
async def test_exception_in_close_is_swallowed():
    output = _RaisingAcloseOutput()
    # Must not raise: a failing close during cancellation must not prevent the
    # task state from being written.
    await _close(None, output)
    assert output.aclosed == 1
