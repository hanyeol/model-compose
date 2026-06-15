"""Tests for the SpeechToTextTaskAction's I/O matrix.

Two orthogonal stream dimensions:
- `streaming` config (token-level model output): wraps results in StreamChunkIterator
- input shape / `${result[]}` reference: stream-mode yields AsyncIterator

`streaming=True` + collect-mode keeps the container shape (single/list) but
each entry becomes a StreamChunkIterator over its tokens.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, Iterator, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.speech_to_text.common import SpeechToTextTaskAction
from mindor.core.utils.iterators import StreamChunkIterator
from mindor.core.utils.media import MediaSource
from mindor.dsl.schema.action import SpeechToTextModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeSpeechToTextAction(SpeechToTextTaskAction):
    """Deterministic `_transcribe` for testing.

    Each MediaSource is identified by its `format` attribute (used as a label).
    - non-streaming: returns [ "<label>" for each audio ]
    - streaming: returns [ Iterator yielding "tok-0", "tok-1", ... for each audio ]
    """

    def __init__(self, config: SpeechToTextModelActionConfig, stream_chunks: int = 3):
        super().__init__(config, device=None)
        self.stream_chunks: int = stream_chunks
        self.batches_seen: List[List[str]] = []

    async def _transcribe(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool) -> Union[List[str], List[Iterator[str]]]:
        labels = [ _label(a) for a in audios ]
        self.batches_seen.append(labels)

        if streaming:
            n = self.stream_chunks

            def _stream() -> Iterator[str]:
                for i in range(n):
                    yield f"tok-{i}"

            return [ _stream() for _ in labels ]

        return labels


def _label(audio: MediaSource) -> str:
    """Recover the label embedded in a MediaSource via its format attribute."""
    return audio.format or "?"


def _media(label: str) -> MediaSource:
    """Build a placeholder MediaSource whose `format` carries the label."""
    return MediaSource(stream=MagicMock(), format=label)


def _make_config(
    audio_expr: Any,
    *,
    output: Any = None,
    batch_size: int = 2,
    streaming: Any = False,
) -> SpeechToTextModelActionConfig:
    raw: dict = {
        "audio":      audio_expr,
        "batch_size": batch_size,
        "streaming":  streaming,
    }
    if output is not None:
        raw["output"] = output
    return SpeechToTextModelActionConfig.model_validate(raw)


def _make_context(audio_value: Any) -> ComponentActionContext:
    """Mock context wrapping the configured audio value through render_audio.

    `audio_value` may be:
      - str label → single MediaSource
      - list of str labels → List[MediaSource]
      - zero-arg callable returning an AsyncIterator of labels → AsyncIterator[MediaSource]
    """
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        if isinstance(value, str):
            return f"${{{key}" in value
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
            if value.startswith("${result[].") and value.endswith("}"):
                attr = value[len("${result[]."):-1]
                target = sources.get("result[]")
                return getattr(target, attr, None) if not isinstance(target, str) else None
            if value.startswith("${result.") and value.endswith("}"):
                attr = value[len("${result."):-1]
                target = sources.get("result")
                return getattr(target, attr, None) if not isinstance(target, str) else None
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    async def render_audio(_value):
        if callable(audio_value) and not isinstance(audio_value, str):
            source = audio_value()
            assert isinstance(source, AsyncIterator)

            async def _map():
                async for label in source:
                    yield _media(label)
            return _map()
        if isinstance(audio_value, list):
            return [ _media(label) for label in audio_value ]
        return _media(audio_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


async def _make_async_iter(items: List[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestSingleInput:
    @pytest.mark.anyio
    async def test_no_output_returns_string(self):
        action = _FakeSpeechToTextAction(_make_config("${input.audio}"))
        ctx    = _make_context("hello")
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == "hello"
        assert action.batches_seen == [ [ "hello" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_string(self):
        action = _FakeSpeechToTextAction(_make_config("${input.audio}", output="${result}"))
        ctx    = _make_context("hi")
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == "hi"

    @pytest.mark.anyio
    async def test_stream_output_yields_one(self):
        action = _FakeSpeechToTextAction(_make_config("${input.audio}", output="${result[]}"))
        ctx    = _make_context("hi")
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "hi" ]


class TestListInput:
    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        action = _FakeSpeechToTextAction(_make_config("${input.audios}"))
        ctx    = _make_context([ "a", "bb", "ccc", "dddd" ])
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == [ "a", "bb", "ccc", "dddd" ]
        # batch_size=2 -> two batches
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc", "dddd" ] ]

    @pytest.mark.anyio
    async def test_stream_output_yields_each(self):
        action = _FakeSpeechToTextAction(_make_config("${input.audios}", output="${result[]}"))
        ctx    = _make_context([ "a", "bb", "ccc" ])
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "a", "bb", "ccc" ]


class TestStreamInput:
    """AsyncIterator input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        def _make_iter():
            return _make_async_iter([ "a", "bb", "ccc" ])

        action = _FakeSpeechToTextAction(_make_config("${input.audios}"))
        ctx    = _make_context(_make_iter)
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "a", "bb", "ccc" ]
        # batch_size=2 -> two batches: ["a", "bb"] and ["ccc"]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_async_iterator(self):
        def _make_iter():
            return _make_async_iter([ "a", "bb" ])

        action = _FakeSpeechToTextAction(_make_config("${input.audios}", output="${result}"))
        ctx    = _make_context(_make_iter)
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "a", "bb" ]

    @pytest.mark.anyio
    async def test_stream_output_template_returns_async_iterator(self):
        def _make_iter():
            return _make_async_iter([ "a", "bb", "ccc", "dddd" ])

        action = _FakeSpeechToTextAction(_make_config("${input.audios}", output="${result[]}"))
        ctx    = _make_context(_make_iter)
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "a", "bb", "ccc", "dddd" ]


class TestTokenStreaming:
    """`streaming=True`: model emits tokens; output container shape depends on input/output."""

    @pytest.mark.anyio
    async def test_single_returns_chunk_iterator(self):
        action = _FakeSpeechToTextAction(
            _make_config("${input.audio}", streaming=True, batch_size=1),
            stream_chunks=3,
        )
        ctx    = _make_context("hello")
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        # collect mode + streaming → single StreamChunkIterator over the row's tokens.
        assert isinstance(result, StreamChunkIterator)
        items = await _collect(result)
        assert items == [ "tok-0", "tok-1", "tok-2" ]

    @pytest.mark.anyio
    async def test_list_returns_list_of_chunk_iterators(self):
        action = _FakeSpeechToTextAction(
            _make_config("${input.audios}", streaming=True, batch_size=2),
            stream_chunks=2,
        )
        ctx    = _make_context([ "a", "bb" ])
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        # collect mode + streaming → List[StreamChunkIterator], one per row.
        assert isinstance(result, list) and len(result) == 2
        assert all(isinstance(item, StreamChunkIterator) for item in result)

        # Drain each row's iterator. Both rows produced 2 tokens.
        outputs = [ await _collect(it) for it in result ]
        assert outputs == [ [ "tok-0", "tok-1" ], [ "tok-0", "tok-1" ] ]

    @pytest.mark.anyio
    async def test_stream_input_streaming_flattens_tokens(self):
        """AsyncIterator input + streaming: tokens of all inputs are flattened."""
        def _make_iter():
            return _make_async_iter([ "a", "bb" ])

        action = _FakeSpeechToTextAction(
            _make_config("${input.audios}", streaming=True, batch_size=1),
            stream_chunks=2,
        )
        ctx    = _make_context(_make_iter)
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        # Two inputs, each producing 2 token chunks -> 4 total
        assert items == [ "tok-0", "tok-1", "tok-0", "tok-1" ]
        assert action.batches_seen == [ [ "a" ], [ "bb" ] ]

    @pytest.mark.anyio
    async def test_stream_output_template_streaming_flattens_tokens(self):
        """${result[]} + streaming: tokens of all inputs are flattened into one AsyncIterator."""
        action = _FakeSpeechToTextAction(
            _make_config("${input.audios}", streaming=True, batch_size=1, output="${result[]}"),
            stream_chunks=2,
        )
        ctx    = _make_context([ "a", "bb" ])
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "tok-0", "tok-1", "tok-0", "tok-1" ]
