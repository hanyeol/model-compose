"""Tests for the TextToTextTaskAction's I/O matrix.

Same structure as ``test_text_generation.py``: exercises the collect vs stream
paths and the ``streaming`` token dimension. The action input field is ``text``
(source text to transform), whereas text-generation uses ``prompt``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, Iterator, List, Union

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_to_text.common import TextToTextTaskAction
from mindor.dsl.schema.action import TextToTextModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeTextToTextAction(TextToTextTaskAction):
    """Deterministic ``_generate`` for testing.

    Matches the current source contract:
    ``async _generate(texts, params, streaming, loop) -> List[str] | List[Iterator[str]]``.

    - non-streaming → ``[ "<text>#0" for text in texts ]``
    - streaming     → ``[ <sync iterator yielding tok-0, tok-1, ...> for each text ]``
    """

    def __init__(self, config: TextToTextModelActionConfig, stream_chunks: int = 3):
        super().__init__(config)
        self.stream_chunks = stream_chunks
        self.batches_seen: List[List[str]] = []

    async def _generate(
        self,
        texts: List[str],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[str], List[Iterator[str]]]:
        self.batches_seen.append(list(texts))
        if streaming:
            n = self.stream_chunks

            def _stream():
                for i in range(n):
                    yield f"tok-{i}"

            return [ _stream() for _ in texts ]

        return [ f"{t}#0" for t in texts ]


def _make_config(
    text_expr: Any,
    output: Any = None,
    batch_size: int = 2,
    streaming: Any = False,
) -> TextToTextModelActionConfig:
    raw: dict = {
        "text": text_expr,
        "batch_size": batch_size,
        "streaming": streaming,
    }
    if output is not None:
        raw["output"] = output
    return TextToTextModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _collect(stream) -> list:
    return [ item async for item in stream ]


class TestSingleInput:
    @pytest.mark.anyio
    async def test_no_output_returns_single(self):
        action = _FakeTextToTextAction(_make_config("${input.text}"))
        ctx = ComponentActionContext("r-1", { "text": "hello" })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == "hello#0"
        assert action.batches_seen == [ [ "hello" ] ]


class TestListInput:
    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        action = _FakeTextToTextAction(_make_config("${input.texts}"))
        ctx = ComponentActionContext("r-3", { "texts": [ "a", "bb", "ccc", "dddd" ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == [ "a#0", "bb#0", "ccc#0", "dddd#0" ]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc", "dddd" ] ]


class TestStreamInput:
    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        action = _FakeTextToTextAction(_make_config("${input.texts}"))
        stream = _make_async_iter([ "a", "bb", "ccc" ])
        ctx = ComponentActionContext("r-5", { "texts": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "a#0", "bb#0", "ccc#0" ]
        # batch_size=2 -> two batches: ["a", "bb"] and ["ccc"]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc" ] ]

    @pytest.mark.anyio
    async def test_direct_output_returns_async_iterator(self):
        action = _FakeTextToTextAction(_make_config("${input.texts}", output="${result}"))
        stream = _make_async_iter([ "a", "bb" ])
        ctx = ComponentActionContext("r-6", { "texts": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "a#0", "bb#0" ]


class TestTokenStreaming:
    """``streaming`` config: each result is a sync token iterator wrapped per-row."""

    @pytest.mark.anyio
    async def test_token_stream_returns_chunk_iterator_for_single_input(self):
        action = _FakeTextToTextAction(
            _make_config("${input.text}", streaming=True, batch_size=1),
            stream_chunks=3,
        )
        ctx = ComponentActionContext("r-9", { "text": "hello" })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, StreamChunkIterator)
        items = await _collect(result)
        assert items == [ "tok-0", "tok-1", "tok-2" ]

    @pytest.mark.anyio
    async def test_token_stream_list_input_returns_list_of_chunk_iterators(self):
        action = _FakeTextToTextAction(
            _make_config("${input.texts}", streaming=True, batch_size=1),
            stream_chunks=2,
        )
        ctx = ComponentActionContext("r-11", { "texts": [ "a", "bb" ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(row, StreamChunkIterator) for row in result)
        tokens = [ await _collect(row) for row in result ]
        assert tokens == [ ["tok-0", "tok-1"], ["tok-0", "tok-1"] ]

    @pytest.mark.anyio
    async def test_token_stream_async_iterator_input_yields_stream_of_chunk_iterators(self):
        action = _FakeTextToTextAction(
            _make_config("${input.texts}", streaming=True, batch_size=1),
            stream_chunks=2,
        )
        stream = _make_async_iter([ "a", "bb" ])
        ctx = ComponentActionContext("r-10", { "texts": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        rows = await _collect(result)
        assert len(rows) == 2
        assert all(isinstance(row, StreamChunkIterator) for row in rows)
        tokens = [ await _collect(row) for row in rows ]
        assert tokens == [ ["tok-0", "tok-1"], ["tok-0", "tok-1"] ]
