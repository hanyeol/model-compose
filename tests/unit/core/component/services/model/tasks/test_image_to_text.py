"""Tests for the ImageToTextTaskAction's I/O matrix.

Two stream dimensions:
- ``streaming`` config (token-level model output) — each generated result is a sync
  iterator yielding tokens, wrapped into a ``StreamChunkIterator`` per row.
- input shape / ``${result[]}`` reference — AsyncIterator input yields per-batch
  ``async_generator``; list/single input goes through the collect path.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, Iterator, List, Optional, Union

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.image_to_text.common import ImageToTextTaskAction
from mindor.core.foundation.cancellation import CancellationToken
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _img(label: str) -> PILImage.Image:
    """Build a tiny image; we identify it via filename attr for assertions."""
    image = PILImage.new("RGB", (2, 2))
    image.filename = label
    return image


def _label(image: PILImage.Image) -> str:
    return getattr(image, "filename", "?")


class _FakeImageToTextAction(ImageToTextTaskAction):
    """Deterministic `_generate` for testing.

    Matches the source contract: ``_generate(images, texts, params, streaming, loop)``.

    - non-streaming → returns ``[ "<image-label>:<text or _>" for each (image, text) ]``
    - streaming     → returns ``[ <sync iterator yielding tok-0, tok-1, ...> for each image ]``
      (each iterator is passed into ``SyncGeneratorStreamer`` by the source.)
    """

    def __init__(self, config: ImageToTextModelActionConfig, stream_chunks: int = 3):
        super().__init__(config)
        self.stream_chunks = stream_chunks
        self.batches_seen: List[List[str]] = []

    async def _generate(
        self,
        images: List[PILImage.Image],
        texts: Optional[List[str]],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[Iterator[str]]]:
        labels = [ _label(img) for img in images ]
        self.batches_seen.append(labels)

        if streaming:
            n = self.stream_chunks
            def _stream():
                for i in range(n):
                    yield f"tok-{i}"
            return [ _stream() for _ in labels ]

        if texts is None:
            return [ f"{label}:_" for label in labels ]
        if len(texts) != len(labels):
            raise ValueError(f"images and texts have different lengths: {len(labels)} vs {len(texts)}")
        return [ f"{label}:{text}" for label, text in zip(labels, texts) ]


def _make_config(
    image_expr: Any,
    text_expr: Any = None,
    output: Any = None,
    batch_size: int = 2,
    streaming: Any = False,
) -> ImageToTextModelActionConfig:
    raw: dict = {
        "image": image_expr,
        "batch_size": batch_size,
        "streaming": streaming,
    }
    if text_expr is not None:
        raw["prompt"] = text_expr
    if output is not None:
        raw["output"] = output
    return ImageToTextModelActionConfig.model_validate(raw)


async def _make_async_iter(items: list) -> AsyncIterator:
    for item in items:
        yield item


async def _collect(stream) -> list:
    return [ item async for item in stream ]


class TestSingleImage:
    @pytest.mark.anyio
    async def test_no_text_no_output_returns_single(self):
        action = _FakeImageToTextAction(_make_config("${input.image}"))
        ctx = ComponentActionContext("r-1", { "image": _img("A") })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == "A:_"
        assert action.batches_seen == [ [ "A" ] ]

    @pytest.mark.anyio
    async def test_with_text_pairs(self):
        action = _FakeImageToTextAction(_make_config("${input.image}", text_expr="${input.text}"))
        ctx = ComponentActionContext("r-2", { "image": _img("A"), "text": "describe" })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == "A:describe"


class TestListImage:
    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        action = _FakeImageToTextAction(_make_config("${input.images}"))
        ctx = ComponentActionContext("r-4", { "images": [ _img("A"), _img("B"), _img("C"), _img("D") ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == [ "A:_", "B:_", "C:_", "D:_" ]
        assert action.batches_seen == [ [ "A", "B" ], [ "C", "D" ] ]

    @pytest.mark.anyio
    async def test_list_image_with_list_text_zips(self):
        action = _FakeImageToTextAction(_make_config("${input.images}", text_expr="${input.texts}"))
        ctx = ComponentActionContext("r-5", { "images": [ _img("A"), _img("B") ], "texts": [ "x", "y" ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert result == [ "A:x", "B:y" ]

    @pytest.mark.anyio
    async def test_list_image_with_shorter_text_raises(self):
        action = _FakeImageToTextAction(_make_config("${input.images}", text_expr="${input.texts}"))
        ctx = ComponentActionContext("r-5a", { "images": [ _img("A"), _img("B"), _img("C") ], "texts": [ "x", "y" ] })
        loop = asyncio.get_running_loop()

        with pytest.raises(ValueError, match="different lengths"):
            await action.run(ctx, loop)

    @pytest.mark.anyio
    async def test_list_image_with_longer_text_raises(self):
        action = _FakeImageToTextAction(_make_config("${input.images}", text_expr="${input.texts}"))
        ctx = ComponentActionContext("r-5b", { "images": [ _img("A"), _img("B") ], "texts": [ "x", "y", "z" ] })
        loop = asyncio.get_running_loop()

        with pytest.raises(ValueError, match="different lengths"):
            await action.run(ctx, loop)


class TestStreamImage:
    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        action = _FakeImageToTextAction(_make_config("${input.images}"))
        stream = _make_async_iter([ _img("A"), _img("B"), _img("C") ])
        ctx = ComponentActionContext("r-8", { "images": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == [ "A:_", "B:_", "C:_" ]
        # batch_size=2 -> two batches: ["A", "B"] and ["C"]
        assert action.batches_seen == [ [ "A", "B" ], [ "C" ] ]


class TestTokenStreaming:
    """``streaming`` config: each result is a sync token iterator, wrapped per-row."""

    @pytest.mark.anyio
    async def test_token_stream_returns_chunk_iterator_for_single_image(self):
        action = _FakeImageToTextAction(
            _make_config("${input.image}", streaming=True, batch_size=1),
            stream_chunks=3,
        )
        ctx = ComponentActionContext("r-13", { "image": _img("A") })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        # Single image + streaming → single StreamChunkIterator over the row's tokens.
        assert isinstance(result, StreamChunkIterator)
        items = await _collect(result)
        assert items == [ "tok-0", "tok-1", "tok-2" ]

    @pytest.mark.anyio
    async def test_token_stream_list_input_yields_list_of_chunk_iterators(self):
        action = _FakeImageToTextAction(
            _make_config("${input.images}", streaming=True, batch_size=1),
            stream_chunks=2,
        )
        ctx = ComponentActionContext("r-14", { "images": [ _img("A"), _img("B") ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(row, StreamChunkIterator) for row in result)
        tokens = [ await _collect(row) for row in result ]
        assert tokens == [ ["tok-0", "tok-1"], ["tok-0", "tok-1"] ]

    @pytest.mark.anyio
    async def test_token_stream_async_iterator_input_yields_stream_of_chunk_iterators(self):
        action = _FakeImageToTextAction(
            _make_config("${input.images}", streaming=True, batch_size=1),
            stream_chunks=2,
        )
        stream = _make_async_iter([ _img("A") ])
        ctx = ComponentActionContext("r-15", { "images": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        rows = await _collect(result)
        assert len(rows) == 1
        assert isinstance(rows[0], StreamChunkIterator)
        tokens = await _collect(rows[0])
        assert tokens == [ "tok-0", "tok-1" ]
