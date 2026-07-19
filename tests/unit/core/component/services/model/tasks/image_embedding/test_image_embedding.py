"""Tests for the ImageEmbeddingTaskAction's I/O matrix.

Mirrors ``text_embedding`` — image_embedding has no ``streaming`` config (the model
API is batch-only). The output-shape rule is the same:

    is_stream_input  = isinstance(image, AsyncIterator)
    is_direct_output = output is empty or output == "${result}"

Stream mode  → AsyncIterator yielding per-embedding output.
Collect mode → single value or list, matching the input shape.

Tests cover all combinations of:
- Input shape: single PIL image / List[PIL image] / AsyncIterator[PIL image]
- Output: unspecified / ${result} / ${result[]}
- Batch boundaries (batch_size=2 with 4 inputs produces 2 batches)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.image_embedding.common import ImageEmbeddingTaskAction
from mindor.core.foundation.cancellation import CancellationToken
from mindor.dsl.schema.action import ImageEmbeddingModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _img(label: str) -> PILImage.Image:
    image = PILImage.new("RGB", (2, 2))
    image.filename = label
    return image


def _label(image: PILImage.Image) -> str:
    return getattr(image, "filename", "?")


class _FakeEmbeddingAction(ImageEmbeddingTaskAction):
    """Deterministic ``_embed`` for testing.

    Each image produces ``[len(label), batch_index]`` so we can verify both the
    batching and per-item dispatch.
    """

    def __init__(self, config: ImageEmbeddingModelActionConfig):
        super().__init__(config)
        self.batches_seen: List[List[str]] = []
        self.params_seen: List[Dict[str, Any]] = []

    async def _embed(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop, cancellation_token: Optional[CancellationToken] = None) -> List[List[float]]:
        labels = [ _label(img) for img in images ]
        self.batches_seen.append(labels)
        self.params_seen.append(params)
        return [ [ float(len(label)), float(i) ] for i, label in enumerate(labels) ]


def _make_config(image_expr: Any, output: Any = None, batch_size: int = 2) -> ImageEmbeddingModelActionConfig:
    raw: dict = { "image": image_expr, "batch_size": batch_size }
    if output is not None:
        raw["output"] = output
    return ImageEmbeddingModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[PILImage.Image]) -> AsyncIterator[PILImage.Image]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestSingleInput:
    """Single PIL image input → single embedding."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_embedding(self):
        action = _FakeEmbeddingAction(_make_config("${input.image}"))
        ctx    = ComponentActionContext("r-1", { "image": _img("hello") })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert result == [ 5.0, 0.0 ]
        assert action.batches_seen == [ [ "hello" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_embedding(self):
        action = _FakeEmbeddingAction(_make_config("${input.image}", output="${result}"))
        ctx    = ComponentActionContext("r-2", { "image": _img("hi") })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert result == [ 2.0, 0.0 ]

    # NOTE: ``output="${result[]}"`` on collect-mode (single/list) input is unsupported
    # by image_embedding — the source only enters the stream-emitting branch when the
    # input is an AsyncIterator. See TestStreamInput tests below for the streaming
    # equivalent.


class TestListInput:
    """List[PIL image] input, batch_size=2 with 4 items → 2 batches."""

    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        action = _FakeEmbeddingAction(_make_config("${input.images}"))
        ctx    = ComponentActionContext(
            "r-4",
            { "images": [ _img("a"), _img("bb"), _img("ccc"), _img("dddd") ] },
        )
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert len(result) == 4
        assert result[0] == [ 1.0, 0.0 ]
        assert result[1] == [ 2.0, 1.0 ]
        assert result[2] == [ 3.0, 0.0 ]
        assert result[3] == [ 4.0, 1.0 ]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc", "dddd" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_list(self):
        action = _FakeEmbeddingAction(_make_config("${input.images}", output="${result}"))
        ctx    = ComponentActionContext("r-5", { "images": [ _img("x"), _img("y") ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert len(result) == 2


class TestStreamInput:
    """AsyncIterator[PIL image] input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        action = _FakeEmbeddingAction(_make_config("${input.images}"))
        stream = _make_async_iter([ _img("a"), _img("bb"), _img("ccc") ])
        ctx    = ComponentActionContext("r-7", { "images": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 3
        # batch_size=2 → two batches: ["a", "bb"] and ["ccc"]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_async_iterator(self):
        action = _FakeEmbeddingAction(_make_config("${input.images}", output="${result}"))
        stream = _make_async_iter([ _img("a"), _img("bb") ])
        ctx    = ComponentActionContext("r-8", { "images": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 2

    @pytest.mark.anyio
    async def test_stream_output_returns_async_iterator(self):
        action = _FakeEmbeddingAction(_make_config("${input.images}", output="${result[]}"))
        stream = _make_async_iter([ _img("a"), _img("bb"), _img("ccc"), _img("dddd") ])
        ctx    = ComponentActionContext("r-9", { "images": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 4


class TestParamsPropagation:
    """``_resolve_params`` builds the dict that the driver consumes via ``_embed``."""

    @pytest.mark.anyio
    async def test_default_params_dict_keys(self):
        action = _FakeEmbeddingAction(_make_config("${input.image}"))
        ctx    = ComponentActionContext("r-10", { "image": _img("hi") })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        assert len(action.params_seen) == 1
        params = action.params_seen[0]
        assert set(params.keys()) >= { "pooling", "normalize" }
        assert params["pooling"] == "cls"
        assert params["normalize"] is True

    @pytest.mark.anyio
    async def test_custom_params_propagate(self):
        raw = {
            "image": "${input.image}",
            "batch_size": 1,
            "params": { "pooling": "mean", "normalize": False },
        }
        cfg    = ImageEmbeddingModelActionConfig.model_validate(raw)
        action = _FakeEmbeddingAction(cfg)
        ctx    = ComponentActionContext("r-11", { "image": _img("hi") })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        params = action.params_seen[0]
        assert params["pooling"] == "mean"
        assert params["normalize"] is False


class TestSchemaValidation:
    """DSL schema-level validation for the image-embedding component config."""

    def test_huggingface_clip_config_validates(self):
        from pydantic import TypeAdapter
        from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceImageEmbeddingModelArchitecture

        cfg = TypeAdapter(ModelComponentConfig).validate_python({
            "type": "model",
            "task": "image-embedding",
            "driver": "huggingface",
            "architecture": "clip",
            "model": "openai/clip-vit-base-patch32",
            "actions": [ { "image": "a.jpg" } ],
        })

        assert cfg.architecture == HuggingfaceImageEmbeddingModelArchitecture.CLIP
        assert cfg.actions[0].params.pooling == "cls"
        assert cfg.actions[0].params.normalize is True

    def test_huggingface_dinov2_config_validates(self):
        from pydantic import TypeAdapter
        from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceImageEmbeddingModelArchitecture

        cfg = TypeAdapter(ModelComponentConfig).validate_python({
            "type": "model",
            "task": "image-embedding",
            "driver": "huggingface",
            "architecture": "dinov2",
            "model": "facebook/dinov2-base",
            "actions": [ {
                "image": [ "a.jpg", "b.jpg" ],
                "batch_size": 4,
                "params": { "pooling": "mean", "normalize": False },
            } ],
        })

        assert cfg.architecture == HuggingfaceImageEmbeddingModelArchitecture.DINOV2
        assert cfg.actions[0].batch_size == 4
        assert cfg.actions[0].params.pooling == "mean"
        assert cfg.actions[0].params.normalize is False

    def test_huggingface_architecture_defaults_to_auto(self):
        from pydantic import TypeAdapter
        from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceImageEmbeddingModelArchitecture

        cfg = TypeAdapter(ModelComponentConfig).validate_python({
            "type": "model",
            "task": "image-embedding",
            "driver": "huggingface",
            "model": "facebook/dinov2-base",
        })

        assert cfg.architecture == HuggingfaceImageEmbeddingModelArchitecture.AUTO
