"""Tests for the ShellAction, covering non-streaming and streaming modes."""

import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.shell import ShellAction
from mindor.dsl.schema.action import ShellActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_context() -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        if key == "result[]" and isinstance(value, str):
            return "${result[]" in value
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        return value

    ctx.render_variable = AsyncMock(side_effect=render_variable)

    from mindor.core.foundation.variable.array import ArrayValue

    async def render_array(value, **kwargs):
        if isinstance(value, list):
            return ArrayValue(value)
        return value
    ctx.render_array = AsyncMock(side_effect=render_array)

    async def render_text(value, **kwargs):
        return value
    ctx.render_text = AsyncMock(side_effect=render_text)

    return ctx


def _make_action(output: Any = None, **kwargs) -> ShellAction:
    payload = {"command": ["echo", "hello"], **kwargs}
    if output is not None:
        payload["output"] = output
    config = ShellActionConfig(**payload)
    return ShellAction(config, base_dir=None, env=None)


class TestNonStreamingMode:
    @pytest.mark.anyio
    async def test_simple_echo(self):
        action = _make_action()
        ctx = _make_context()

        result = await action.run(ctx)

        assert isinstance(result, dict)
        assert result["stdout"] == "hello"
        assert result["exit_code"] == 0

    @pytest.mark.anyio
    async def test_multiline_output_collected(self):
        action = _make_action(command=[sys.executable, "-c", "print('a'); print('b'); print('c')"])
        ctx = _make_context()

        result = await action.run(ctx)

        assert result["stdout"] == "a\nb\nc"
        assert result["exit_code"] == 0

    @pytest.mark.anyio
    async def test_nonzero_exit_code_captured(self):
        action = _make_action(command=[sys.executable, "-c", "import sys; sys.exit(7)"])
        ctx = _make_context()

        result = await action.run(ctx)

        assert result["exit_code"] == 7


class TestStreamingMode:
    @pytest.mark.anyio
    async def test_streaming_yields_lines_as_iterator(self):
        action = _make_action(
            command=[sys.executable, "-c", "print('a'); print('b'); print('c')"],
            streaming=True,
        )
        ctx = _make_context()

        result = await action.run(ctx)

        from collections.abc import AsyncIterable
        assert isinstance(result, AsyncIterable)
        items = [item async for item in result]
        assert items == ["a\n", "b\n", "c\n"]

    @pytest.mark.anyio
    async def test_streaming_empty_output(self):
        action = _make_action(command=[sys.executable, "-c", "pass"], streaming=True)
        ctx = _make_context()

        result = await action.run(ctx)

        items = [item async for item in result]
        assert items == []
