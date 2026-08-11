"""Async / contract tests for the NativeTranscriptCorrector action.

Focus areas (complements the pure-corrector unit tests in test_native.py):

- Contract: driving `NativeTranscriptCorrectorAction(config).run(context)` end-to-end
  through the shared async wrapper returns the expected corrected segments.
- Input matrix mirrors the sentence-splitter model:
    * ``List[Segment]`` — single transcript, batched
    * ``StreamChunkIterator(is_fragmented=True)`` of segments — single transcript, live stream
    * ``List[List[Segment]]`` — multiple transcripts, batched
    * ``AsyncIterator[List[Segment]]`` — multiple transcripts, streaming outer
- ``streaming=True`` wraps per-transcript output in a ``StreamChunkIterator``.
- Non-blocking: because feed/flush and corrector construction are synchronous CPU
  work, they must be offloaded via ``_run_in_executor``. Verified by patching in
  a slowed-down corrector and asserting an asyncio ticker keeps advancing.
- Service ``_run`` signature: `(self, action, context)`, no `loop` kwarg.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Dict, Iterator, List, Optional
from unittest.mock import patch

import pytest

from mindor.core.component.services.transcript_corrector.drivers.native import (
    NativeTranscriptCorrectorAction,
    NativeTranscriptCorrectorService,
    NativeStreamingTranscriptCorrector,
)
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.dsl.schema.action import NativeTranscriptCorrectorActionConfig

from tests.async_helpers import (
    assert_does_not_block,
    collect_async,
    make_action_context,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _seg(text: str, start: float, end: float, **extra: Any) -> Dict[str, Any]:
    return {"text": text, "start_time": start, "end_time": end, **extra}


async def _async_iter(items):
    for item in items:
        yield item


class _SlowStreamingCorrector(NativeStreamingTranscriptCorrector):
    """A corrector whose feed/flush pause the calling thread so the
    ``assert_does_not_block`` ticker has meaningful wall time to accumulate.
    The actual alignment logic is inherited unchanged."""

    def __init__(self, *args, sleep_s: float = 0.05, **kwargs):
        super().__init__(*args, **kwargs)
        self.sleep_s = sleep_s

    def feed(self, segment: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        time.sleep(self.sleep_s)
        yield from super().feed(segment)

    def flush(self) -> Iterator[Dict[str, Any]]:
        time.sleep(self.sleep_s)
        yield from super().flush()


class TestSingleTranscriptListInput:
    """A single list of segments is treated as one transcript; result is a
    single list of corrected segments (not wrapped in an outer list)."""

    @pytest.mark.anyio
    async def test_returns_flat_list_of_corrected_segments(self):
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world this is a test",
            transcript=[
                _seg("helo wrld", 0.0, 1.0),
                _seg("this is a tst", 1.0, 2.0),
            ],
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)

        assert isinstance(result, list)
        assert [r["text"] for r in result] == ["hello world", "this is a test"]

    @pytest.mark.anyio
    async def test_empty_transcript_still_emits_reference_as_estimated(self):
        # With no STT segments at all, the reference surfaces on flush as
        # estimated gap segments — the corrector guarantees full coverage of
        # the reference text.
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=[],
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert isinstance(result, list) and result
        assert all(seg.get("estimated") for seg in result)
        assert " ".join(seg["text"] for seg in result) == "hello world"

    @pytest.mark.anyio
    async def test_reference_list_is_joined_with_spaces(self):
        # Reference passed as list of strings should behave like a joined string.
        config = NativeTranscriptCorrectorActionConfig(
            reference=["hello", "world", "this is a test"],
            transcript=[_seg("helo wrld this is a tst", 0.0, 1.0)],
        )
        context = make_action_context()
        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert result[0]["text"] == "hello world this is a test"

    @pytest.mark.anyio
    async def test_variable_interpolation_from_input(self):
        # ``${input.field}`` should resolve through the real context/renderer.
        config = NativeTranscriptCorrectorActionConfig(
            reference="${input.ref}",
            transcript="${input.segments}",
        )
        context = make_action_context(
            input={
                "ref": "hello world",
                "segments": [_seg("helo wrld", 0.0, 1.0)],
            },
        )

        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert result[0]["text"] == "hello world"


class TestSingleTranscriptFragmentedStream:
    """A ``StreamChunkIterator(is_fragmented=True)`` of segments represents a
    single transcript being streamed live (the subtitle use case)."""

    @pytest.mark.anyio
    async def test_fragmented_stream_returns_stream_of_corrected_segments(self):
        segments = [
            _seg("helo wrld", 0.0, 1.0),
            _seg("this is a tst", 1.0, 2.0),
        ]
        stream = StreamChunkIterator(_async_iter(segments), is_fragmented=True)

        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world this is a test",
            transcript=stream,
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        # Fragmented input is a single transcript; without streaming=True the
        # collected result is a flat list.
        assert isinstance(result, list)
        assert [r["text"] for r in result] == ["hello world", "this is a test"]

    @pytest.mark.anyio
    async def test_fragmented_stream_with_streaming_output(self):
        segments = [
            _seg("helo wrld", 0.0, 1.0),
            _seg("this is a tst", 1.0, 2.0),
        ]
        stream = StreamChunkIterator(_async_iter(segments), is_fragmented=True)

        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world this is a test",
            transcript=stream,
            streaming=True,
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        # Single-transcript + streaming=True returns a StreamChunkIterator directly.
        assert isinstance(result, StreamChunkIterator)
        chunks = await collect_async(result)
        assert [c["text"] for c in chunks] == ["hello world", "this is a test"]


class TestMultiTranscriptListInput:
    """A python list whose elements are themselves transcripts (lists of
    segments) processes multiple transcripts, one corrector each."""

    @pytest.mark.anyio
    async def test_batch_input_returns_list_of_lists(self):
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=[
                [_seg("helo wrld", 0.0, 1.0)],
                [_seg("hello world", 2.0, 3.0)],
            ],
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert isinstance(result, list)
        assert len(result) == 2
        assert [t[0]["text"] for t in result] == ["hello world", "hello world"]

    @pytest.mark.anyio
    async def test_each_transcript_uses_its_own_corrector_state(self):
        # If correctors were shared, the second transcript would find the
        # reference cursor already at the end and emit nothing.
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=[
                [_seg("helo wrld", 0.0, 1.0)],
                [_seg("helo wrld", 2.0, 3.0)],
            ],
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert len(result[0]) == 1
        assert len(result[1]) == 1  # NOT zero — independent cursors

    @pytest.mark.anyio
    async def test_multi_transcript_streaming_wraps_each_in_stream_chunk_iterator(self):
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=[
                [_seg("helo wrld", 0.0, 1.0)],
                [_seg("hello world", 2.0, 3.0)],
            ],
            streaming=True,
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert isinstance(result, list)
        assert len(result) == 2
        for per_transcript in result:
            assert isinstance(per_transcript, StreamChunkIterator)

        drained = [await collect_async(s) for s in result]
        assert [d[0]["text"] for d in drained] == ["hello world", "hello world"]


class TestMultiTranscriptStreamingInput:
    """A non-fragmented AsyncIterator whose elements are transcripts (lists or
    inner streams). Outer path returns a StreamChunkIterator of per-transcript
    results."""

    @pytest.mark.anyio
    async def test_async_iter_of_lists_returns_outer_stream(self):
        transcripts = [
            [_seg("helo wrld", 0.0, 1.0)],
            [_seg("hello world", 2.0, 3.0)],
        ]
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=_async_iter(transcripts),
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        # Streaming outer → the run() returns an async iterator over per-transcript results.
        drained = await collect_async(result)
        assert len(drained) == 2
        assert [t[0]["text"] for t in drained] == ["hello world", "hello world"]

    @pytest.mark.anyio
    async def test_async_iter_of_inner_streams(self):
        # Fully-nested: outer stream, inner stream. This is the "many
        # transcripts, each streamed live" case.
        async def _inner1():
            yield _seg("helo wrld", 0.0, 1.0)

        async def _inner2():
            yield _seg("hello world", 2.0, 3.0)

        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=_async_iter([_inner1(), _inner2()]),
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        drained = await collect_async(result)
        assert [t[0]["text"] for t in drained] == ["hello world", "hello world"]


class TestOutputInterpolation:
    """When ``output`` is set, results (or per-chunk values in streaming mode)
    flow through the renderer."""

    @pytest.mark.anyio
    async def test_output_template_transforms_flat_list_result(self):
        config = NativeTranscriptCorrectorActionConfig(
            reference="hello world",
            transcript=[_seg("helo wrld", 0.0, 1.0)],
            output="${result[0].text}",
        )
        context = make_action_context()

        result = await NativeTranscriptCorrectorAction(config).run(context)
        assert result == "hello world"


class TestNonBlocking:
    """The sync corrector must be offloaded via ``_run_in_executor``."""

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self):
        # Enough segments that per-feed sleep adds up to noticeable wall time.
        segments = [_seg("helo wrld", i * 0.5, (i + 1) * 0.5) for i in range(20)]
        reference = " ".join(["hello world"] * 20)
        config = NativeTranscriptCorrectorActionConfig(
            reference=reference,
            transcript=segments,
        )
        context = make_action_context()

        def _slow_factory(**kwargs):
            return _SlowStreamingCorrector(sleep_s=0.05, **kwargs)

        with patch(
            "mindor.core.component.services.transcript_corrector.drivers.native.NativeStreamingTranscriptCorrector",
            side_effect=_slow_factory,
        ):
            result = await assert_does_not_block(
                NativeTranscriptCorrectorAction(config).run(context),
                tick_interval_s=0.01,
                min_ticks=5,
            )

        # Sanity: at least some segments got corrected.
        assert isinstance(result, list)
        assert len(result) >= 1


class TestServiceSignature:
    """Runtime shape assertions on ``NativeTranscriptCorrectorService._run``."""

    def test_run_has_no_loop_kwarg(self):
        signature = inspect.signature(NativeTranscriptCorrectorService._run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names, (
            f"NativeTranscriptCorrectorService._run should not accept a `loop` kwarg; "
            f"got parameters {param_names!r}"
        )
        assert param_names == ["self", "action", "context"]

    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(NativeTranscriptCorrectorAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "context"]
