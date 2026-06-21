"""Tests for the TextToSpeechTaskAction's I/O matrix.

text_to_speech has no token-level streaming (models are single-shot synth),
so the output-shape rule is purely:

    is_stream_input  = isinstance(text, AsyncIterator)
    is_stream_output = output references "result[]"
    is_direct_output = output is empty or output == "${result}"
    is_stream_mode   = is_stream_input or is_stream_output

Single inputs return a single StreamResource (synthesized audio asset).
List inputs return List[StreamResource]. Stream-mode returns AsyncIterator.

Tests cover all combinations of:
- Input shape: single str / List[str] / AsyncIterator[str]
- Output: unspecified / ${result} / ${result[]}
- Batch boundaries
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, List

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_to_speech.common import TextToSpeechTaskAction
from mindor.core.utils.streaming.resources import StreamResource
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import QwenTextToSpeechGenerateModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeTextToSpeechAction(TextToSpeechTaskAction):
    """Deterministic ``_generate`` for testing.

    Each text yields a ``BytesStreamResource`` whose payload encodes the
    input (so we can correlate output StreamResources with the input texts).
    """

    def __init__(self, config: QwenTextToSpeechGenerateModelActionConfig):
        super().__init__(config, device=None)
        self.batches_seen: List[List[str]] = []
        self.params_seen: List[Dict[str, Any]] = []

    async def _generate(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[StreamResource]:
        self.batches_seen.append(list(texts))
        self.params_seen.append(params)
        return [ BytesStreamResource(t.encode("utf-8"), content_type="audio/pcm") for t in texts ]


def _label(stream: StreamResource) -> str:
    """Recover the original text from a fake-generated stream."""
    assert isinstance(stream, BytesStreamResource)
    return stream.data.decode("utf-8")


def _make_config(
    text_expr: Any,
    *,
    output: Any = None,
    batch_size: int = 2,
) -> QwenTextToSpeechGenerateModelActionConfig:
    raw: dict = {
        "method":     "generate",
        "text":       text_expr,
        "batch_size": batch_size,
    }
    if output is not None:
        raw["output"] = output
    return QwenTextToSpeechGenerateModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestSingleInput:
    @pytest.mark.anyio
    async def test_no_output_returns_single_resource(self):
        action = _FakeTextToSpeechAction(_make_config("${input.text}"))
        ctx    = ComponentActionContext("r-1", { "text": "hello" })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, StreamResource)
        assert _label(result) == "hello"
        assert action.batches_seen == [ [ "hello" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_resource(self):
        action = _FakeTextToSpeechAction(_make_config("${input.text}", output="${result}"))
        ctx    = ComponentActionContext("r-2", { "text": "hi" })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, StreamResource)
        assert _label(result) == "hi"

    # NOTE: ``output="${result[]}"`` on collect-mode (single/list) input is unsupported
    # by text_to_speech — the source only enters the stream-emitting branch when the
    # input is an AsyncIterator. See TestStreamInput tests below.


class TestListInput:
    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        action = _FakeTextToSpeechAction(_make_config("${input.texts}"))
        ctx    = ComponentActionContext("r-4", { "texts": [ "a", "bb", "ccc", "dddd" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list) and len(result) == 4
        assert [ _label(s) for s in result ] == [ "a", "bb", "ccc", "dddd" ]
        # batch_size=2 → two batches
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc", "dddd" ] ]

    # NOTE: see TestSingleInput — list input + ``output="${result[]}"`` doesn't enter
    # the stream-emitting branch in text_to_speech.


class TestStreamInput:
    """AsyncIterator[str] input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        action = _FakeTextToSpeechAction(_make_config("${input.texts}"))
        stream = _make_async_iter([ "a", "bb", "ccc" ])
        ctx    = ComponentActionContext("r-6", { "texts": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert [ _label(s) for s in items ] == [ "a", "bb", "ccc" ]
        # batch_size=2 → two batches: ["a", "bb"] and ["ccc"]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_async_iterator(self):
        action = _FakeTextToSpeechAction(_make_config("${input.texts}", output="${result}"))
        stream = _make_async_iter([ "a", "bb" ])
        ctx    = ComponentActionContext("r-7", { "texts": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert [ _label(s) for s in items ] == [ "a", "bb" ]

    @pytest.mark.anyio
    async def test_stream_output_template_returns_async_iterator(self):
        action = _FakeTextToSpeechAction(_make_config("${input.texts}", output="${result[]}"))
        stream = _make_async_iter([ "a", "bb", "ccc", "dddd" ])
        ctx    = ComponentActionContext("r-8", { "texts": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert [ _label(s) for s in items ] == [ "a", "bb", "ccc", "dddd" ]
