"""Async / contract tests for TextSplitterAction.

Complements test_text_splitter.py by exercising the refactored no-`loop`
run() signature and by asserting that the CPU-bound `StreamingTextSplitter`
work is offloaded from the event loop via `_run_in_executor`.
"""

from __future__ import annotations

import inspect
import time
from typing import Iterator, List
from unittest.mock import patch

import pytest

from mindor.core.component.services.text_splitter import TextSplitterAction
from mindor.core.component.services.text_splitter.text_splitter import (
    StreamingTextSplitter,
    TextSplitterComponent,
)
from mindor.dsl.schema.action import TextSplitterActionConfig

from tests.async_helpers import assert_does_not_block, make_action_context


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _SlowStreamingTextSplitter(StreamingTextSplitter):
    """StreamingTextSplitter that sleeps in feed()/flush() so an event-loop-
    blocking implementation is easy to detect via the ticker helper."""

    def __init__(self, separators, chunk_size, chunk_overlap, sleep_s: float = 0.1):
        super().__init__(separators, chunk_size, chunk_overlap)
        self.sleep_s = sleep_s

    def feed(self, text: str) -> Iterator[str]:
        time.sleep(self.sleep_s)
        yield from super().feed(text)

    def flush(self) -> Iterator[str]:
        time.sleep(self.sleep_s)
        yield from super().flush()


class TestTextSplitterActionContract:
    @pytest.mark.anyio
    async def test_simple_text_returns_list_of_chunks(self):
        # Short input, big chunk → single chunk.
        config = TextSplitterActionConfig(
            text="Hello world.",
            chunk_size=100,
            chunk_overlap=0,
        )
        context = make_action_context()

        result = await TextSplitterAction(config).run(context)

        assert result == ["Hello world."]

    @pytest.mark.anyio
    async def test_batch_input_returns_list_of_lists(self):
        config = TextSplitterActionConfig(
            text=["one two three", "alpha beta"],
            chunk_size=100,
            chunk_overlap=0,
        )
        context = make_action_context()

        result = await TextSplitterAction(config).run(context)

        assert result == [["one two three"], ["alpha beta"]]

    @pytest.mark.anyio
    async def test_variable_interpolation_from_input(self):
        # Real context/renderer path — `${input.text}` must resolve to the
        # value we placed in the input dict.
        config = TextSplitterActionConfig(
            text="${input.text}",
            chunk_size=50,
            chunk_overlap=0,
        )
        context = make_action_context(input={"text": "resolved via renderer"})

        result = await TextSplitterAction(config).run(context)

        assert result == ["resolved via renderer"]


class TestTextSplitterActionNonBlocking:
    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self):
        # Use a big text and patch the splitter with a slow variant so feed()
        # takes long enough that a blocked event loop would be obvious.
        text = ("The quick brown fox jumps over the lazy dog. " * 4000)
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=200,
            chunk_overlap=20,
        )
        context = make_action_context()

        def _slow_factory(seps, chunk_size, chunk_overlap):
            return _SlowStreamingTextSplitter(seps, chunk_size, chunk_overlap, sleep_s=0.1)

        with patch(
            "mindor.core.component.services.text_splitter.text_splitter.StreamingTextSplitter",
            side_effect=_slow_factory,
        ):
            result = await assert_does_not_block(
                TextSplitterAction(config).run(context),
                tick_interval_s=0.01,
                min_ticks=5,
            )

        assert isinstance(result, list)
        assert len(result) > 1


class TestTextSplitterComponentSignature:
    def test_component_run_has_no_loop_kwarg(self):
        signature = inspect.signature(TextSplitterComponent._run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "action", "context"]

    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(TextSplitterAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "context"]
