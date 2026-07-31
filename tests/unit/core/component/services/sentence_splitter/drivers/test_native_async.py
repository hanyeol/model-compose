"""Async / contract tests for the NativeSentenceSplitter action.

Focus areas (complements the pure-splitter unit tests in test_native.py):

- Contract: driving `NativeSentenceSplitterAction(config).run(context)` end-to-end
  through the shared async wrapper returns the same chunk list the raw
  splitter would produce.
- Non-blocking: because the driver's `feed` / `flush` / `_create_splitter`
  are all synchronous, they must be offloaded via `_run_in_executor`. We
  verify this by patching the raw splitter with a version whose per-piece
  work sleeps long enough (~200ms) that a concurrent asyncio ticker would
  stall if execution ran on the event-loop thread.
- Service `_run` signature: `_run(action, context)` with no `loop` kwarg.
- Streaming input path via a `StreamChunkIterator` of separate pieces.
"""

from __future__ import annotations

import inspect
import time
from typing import Iterator, List, Optional
from unittest.mock import patch

import pytest

from mindor.core.component.services.sentence_splitter.drivers.native import (
    NativeSentenceSplitterAction,
    NativeSentenceSplitterService,
    NativeStreamingSentenceSplitter,
)
from mindor.dsl.schema.action import NativeSentenceSplitterActionConfig

from tests.async_helpers import assert_does_not_block, make_action_context


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _SlowStreamingSplitter(NativeStreamingSentenceSplitter):
    """A splitter whose feed/flush pause the calling thread so that the
    `assert_does_not_block` ticker has meaningful wall time to accumulate
    against. The actual splitting logic is inherited unchanged."""

    def __init__(self, min_chunk_length: int, max_chunk_length: Optional[int], sleep_s: float = 0.05):
        super().__init__(min_chunk_length, max_chunk_length)
        self.sleep_s = sleep_s

    def feed(self, text: str) -> Iterator[str]:
        time.sleep(self.sleep_s)
        yield from super().feed(text)

    def flush(self) -> Iterator[str]:
        time.sleep(self.sleep_s)
        yield from super().flush()


class TestNativeSentenceSplitterActionContract:
    """End-to-end drive of NativeSentenceSplitterAction via the shared context."""

    @pytest.mark.anyio
    async def test_simple_paragraph_split_returns_list(self):
        config = NativeSentenceSplitterActionConfig(
            text="First sentence. Second one! Third?",
        )
        context = make_action_context(input={"text": "unused"})

        result = await NativeSentenceSplitterAction(config).run(context)

        assert result == ["First sentence.", "Second one!", "Third?"]

    @pytest.mark.anyio
    async def test_batch_input_returns_list_of_lists(self):
        # A `text` value that's a python list is treated as multiple inputs;
        # each yields its own chunk list.
        config = NativeSentenceSplitterActionConfig(
            text=["A. B.", "One. Two."],
        )
        context = make_action_context()

        result = await NativeSentenceSplitterAction(config).run(context)

        assert isinstance(result, list)
        assert result == [["A.", "B."], ["One.", "Two."]]

    @pytest.mark.anyio
    async def test_variable_interpolation_from_input(self):
        # `${input.text}` should resolve through the real context/renderer
        # to the value provided at context construction.
        config = NativeSentenceSplitterActionConfig(text="${input.text}")
        context = make_action_context(input={"text": "Hi. There."})

        result = await NativeSentenceSplitterAction(config).run(context)

        assert result == ["Hi.", "There."]


class TestNativeSentenceSplitterActionFragmentedInput:
    """A fragmented ``StreamChunkIterator`` (a single logical text delivered in
    pieces) must reach the splitter unconcatenated so pieces can be fed
    incrementally. Regression guard: before ``render_text(collect=False)``, the
    renderer would concatenate the pieces into a single ``str`` and the
    splitter's fragmented branch would be dead code.
    """

    from mindor.core.foundation.streaming.iterators import StreamChunkIterator

    @staticmethod
    async def _pieces(*chunks):
        for chunk in chunks:
            yield chunk

    @pytest.mark.anyio
    async def test_fragmented_stream_produces_full_sentence_list(self):
        from mindor.core.foundation.streaming.iterators import StreamChunkIterator

        fragmented = StreamChunkIterator(
            self._pieces("The quick", " brown fox.", " Jumps over the", " lazy dog."),
            is_fragmented=True,
        )
        config = NativeSentenceSplitterActionConfig(text="${input.text}")
        context = make_action_context(input={"text": fragmented})

        result = await NativeSentenceSplitterAction(config).run(context)

        assert result == ["The quick brown fox.", "Jumps over the lazy dog."]

    @pytest.mark.anyio
    async def test_fragmented_stream_with_streaming_output_yields_incrementally(self):
        # Sanity that streaming=True over a fragmented input returns a stream
        # (not a materialized list) and produces the expected sentences.
        from mindor.core.foundation.streaming.iterators import StreamChunkIterator

        fragmented = StreamChunkIterator(
            self._pieces("Alpha.", " Beta.", " Gamma."),
            is_fragmented=True,
        )
        config = NativeSentenceSplitterActionConfig(text="${input.text}", streaming=True)
        context = make_action_context(input={"text": fragmented})

        result = await NativeSentenceSplitterAction(config).run(context)
        assert isinstance(result, StreamChunkIterator)

        collected = [chunk async for chunk in result]
        assert collected == ["Alpha.", "Beta.", "Gamma."]


class TestNativeSentenceSplitterActionNonBlocking:
    """The sync splitter must be offloaded via `_run_in_executor`."""

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self):
        # Build a large input (~200KB) so the executor path has enough wall
        # time to matter; use the slow-splitter patch so per-piece work adds
        # meaningful blocking time on the executor thread.
        text = ("This is one sentence. " * 5000)  # ~110KB
        config = NativeSentenceSplitterActionConfig(text=text)
        context = make_action_context()

        def _slow_factory(min_len, max_len):
            return _SlowStreamingSplitter(min_len, max_len, sleep_s=0.1)

        with patch(
            "mindor.core.component.services.sentence_splitter.drivers.native.NativeStreamingSentenceSplitter",
            side_effect=_slow_factory,
        ):
            result = await assert_does_not_block(
                NativeSentenceSplitterAction(config).run(context),
                tick_interval_s=0.01,
                min_ticks=5,
            )

        # Sanity: still produced sentences.
        assert isinstance(result, list)
        assert len(result) > 100


class TestNativeSentenceSplitterServiceSignature:
    """Runtime shape assertions on `NativeSentenceSplitterService._run`."""

    def test_run_has_no_loop_kwarg(self):
        signature = inspect.signature(NativeSentenceSplitterService._run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names, (
            f"NativeSentenceSplitterService._run should not accept a `loop` kwarg; "
            f"got parameters {param_names!r}"
        )
        # Positive shape: (self, action, context)
        assert param_names == ["self", "action", "context"]

    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(NativeSentenceSplitterAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "context"]
