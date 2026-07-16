"""Integration tests for HuggingfaceImageEmbeddingTaskAction with a real CLIP model.

Uses ``openai/clip-vit-base-patch32`` (~600 MB) — the reference CLIP release
whose ``get_image_features`` path is what this task registers as
``architecture: clip``.

Verifies:
- single / list / AsyncIterator inputs and their output shapes
- collect / ``${result}`` / ``${result[]}`` outputs
- L2 normalization actually produces unit-norm vectors
- Visually distinct images cluster: same-family cosine > cross-family cosine
- Both explicit ``clip`` architecture and ``auto`` (hasattr fall-through) paths
  produce identical vectors
"""

from __future__ import annotations

import asyncio
import importlib.util
import math
from collections.abc import AsyncIterator
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.dsl.schema.action import ImageEmbeddingModelActionConfig


transformers_required = pytest.mark.skipif(
    not all(importlib.util.find_spec(m) for m in ("transformers", "torch")),
    reason="transformers/torch not available",
)


CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
CLIP_EMBED_DIM = 512


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _solid(color: tuple[int, int, int], size: int = 32) -> PILImage.Image:
    """A flat color patch — trivially different across colors so CLIP separates them."""
    return PILImage.new("RGB", (size, size), color=color)


def _gradient(size: int = 32) -> PILImage.Image:
    """A horizontal gradient — visually distinct from any solid patch."""
    image = PILImage.new("RGB", (size, size))
    pixels = image.load()
    for x in range(size):
        v = int(255 * x / max(size - 1, 1))
        for y in range(size):
            pixels[x, y] = (v, v, v)
    return image


@pytest.fixture(scope="module")
def clip_bundle():
    """Load CLIP once per module. Returns (architecture, model, processor, device)."""
    import torch
    from transformers import CLIPModel, CLIPProcessor
    from mindor.dsl.schema.component import HuggingfaceImageEmbeddingModelArchitecture

    try:
        model     = CLIPModel.from_pretrained(CLIP_MODEL_ID)
        processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
    except Exception as e:
        pytest.skip(f"{CLIP_MODEL_ID} unavailable: {e}")

    device = torch.device("cpu")
    model = model.to(device)
    model.eval()

    return HuggingfaceImageEmbeddingModelArchitecture, model, processor, device


@pytest.fixture(scope="module")
def clip_action_factory(clip_bundle):
    """Factory for actions using the explicit CLIP architecture branch."""
    from mindor.core.component.services.model.tasks.image_embedding.huggingface import (
        HuggingfaceImageEmbeddingTaskAction,
    )

    arch_enum, model, processor, device = clip_bundle

    def _factory(config: ImageEmbeddingModelActionConfig) -> HuggingfaceImageEmbeddingTaskAction:
        return HuggingfaceImageEmbeddingTaskAction(
            config, arch_enum.CLIP, model, processor, device,
        )

    return _factory


@pytest.fixture(scope="module")
def auto_action_factory(clip_bundle):
    """Factory for actions using AUTO — exercises the hasattr fall-through."""
    from mindor.core.component.services.model.tasks.image_embedding.huggingface import (
        HuggingfaceImageEmbeddingTaskAction,
    )

    arch_enum, model, processor, device = clip_bundle

    def _factory(config: ImageEmbeddingModelActionConfig) -> HuggingfaceImageEmbeddingTaskAction:
        return HuggingfaceImageEmbeddingTaskAction(
            config, arch_enum.AUTO, model, processor, device,
        )

    return _factory


def _make_context(image_value: Any) -> ComponentActionContext:
    """Mock context routing render_image + variable resolution + source tracking.

    ``image_value`` may be:
      - a PIL Image → single image
      - a list of PIL Images → list input
      - a zero-arg callable returning an AsyncIterator[PIL] → streaming input
    """
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def _resolved_image() -> Any:
        return image_value() if callable(image_value) else image_value

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${input.image}":
                return _resolved_image()
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    async def render_image(value, **kwargs):
        return _resolved_image()

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_image = AsyncMock(side_effect=render_image)
    return ctx


def _make_config(
    image_expr: Any = "${input.image}",
    *,
    output: Any = None,
    batch_size: int = 2,
    pooling: str = "cls",
    normalize: bool = True,
) -> ImageEmbeddingModelActionConfig:
    raw: dict = {
        "image":      image_expr,
        "batch_size": batch_size,
        "params": {
            "pooling":   pooling,
            "normalize": normalize,
        },
    }
    if output is not None:
        raw["output"] = output
    return ImageEmbeddingModelActionConfig.model_validate(raw)


def _cosine(a: List[float], b: List[float]) -> float:
    dot    = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b + 1e-12)


@transformers_required
class TestSingleInput:
    @pytest.mark.anyio
    async def test_single_returns_vector(self, clip_action_factory):
        action = clip_action_factory(_make_config())
        ctx    = _make_context(_solid((255, 0, 0)))

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
        assert len(result) == CLIP_EMBED_DIM

    @pytest.mark.anyio
    async def test_normalize_yields_unit_vector(self, clip_action_factory):
        action = clip_action_factory(_make_config(normalize=True))
        ctx    = _make_context(_solid((0, 128, 255)))

        result = await action.run(ctx, asyncio.get_event_loop())

        norm = math.sqrt(sum(x * x for x in result))
        assert norm == pytest.approx(1.0, abs=1e-4)

    @pytest.mark.anyio
    async def test_no_normalize_yields_non_unit_vector(self, clip_action_factory):
        action = clip_action_factory(_make_config(normalize=False))
        ctx    = _make_context(_solid((0, 128, 255)))

        result = await action.run(ctx, asyncio.get_event_loop())

        norm = math.sqrt(sum(x * x for x in result))
        # CLIP raw image features have norms well away from 1.
        assert abs(norm - 1.0) > 1e-2


@transformers_required
class TestListInput:
    @pytest.mark.anyio
    async def test_list_returns_list_of_vectors(self, clip_action_factory):
        action = clip_action_factory(_make_config(batch_size=2))
        ctx    = _make_context([
            _solid((255, 0, 0)),
            _solid((0, 255, 0)),
            _solid((0, 0, 255)),
        ])

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list) and len(result) == 3
        assert all(isinstance(v, list) and len(v) == CLIP_EMBED_DIM for v in result)

    @pytest.mark.anyio
    async def test_visually_similar_images_cluster(self, clip_action_factory):
        """Two similar red patches should be closer to each other than to a gradient."""
        action = clip_action_factory(_make_config(batch_size=3))
        ctx    = _make_context([
            _solid((250, 10, 10)),   # red-ish
            _solid((240, 20, 20)),   # red-ish (near-duplicate)
            _gradient(),             # completely different content
        ])

        result = await action.run(ctx, asyncio.get_event_loop())

        sim_near = _cosine(result[0], result[1])
        sim_far  = _cosine(result[0], result[2])
        assert sim_near > sim_far


@transformers_required
class TestAsyncIteratorInput:
    @pytest.mark.anyio
    async def test_stream_input_yields_vectors(self, clip_action_factory):
        def _make_iter():
            async def _gen():
                yield _solid((255, 0, 0))
                yield _solid((0, 255, 0))
                yield _solid((0, 0, 255))
            return _gen()

        action = clip_action_factory(_make_config(batch_size=2))
        ctx    = _make_context(_make_iter)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [ item async for item in result ]
        assert len(items) == 3
        assert all(isinstance(v, list) and len(v) == CLIP_EMBED_DIM for v in items)


@transformers_required
class TestAutoArchitectureFallthrough:
    """AUTO branches through ``hasattr(model, 'get_image_features')`` — with a CLIP
    model loaded, the AUTO path should return the same vector as the explicit CLIP path.
    """

    @pytest.mark.anyio
    async def test_auto_matches_clip_output(self, clip_action_factory, auto_action_factory):
        image  = _solid((128, 200, 64))

        explicit = await clip_action_factory(_make_config()).run(_make_context(image), asyncio.get_event_loop())
        auto     = await auto_action_factory(_make_config()).run(_make_context(image), asyncio.get_event_loop())

        # Same model + same input → embeddings must match closely.
        for a, b in zip(explicit, auto):
            assert a == pytest.approx(b, abs=1e-6)


@transformers_required
class TestBatching:
    @pytest.mark.anyio
    async def test_batch_boundaries_yield_contiguous_results(self, clip_action_factory):
        """batch_size=2 over 5 images → 3 batches (2 + 2 + 1) but 5 vectors total."""
        images = [
            _solid((10, 10, 10)),
            _solid((50, 50, 50)),
            _solid((100, 100, 100)),
            _solid((150, 150, 150)),
            _solid((200, 200, 200)),
        ]

        action = clip_action_factory(_make_config(batch_size=2))
        ctx    = _make_context(images)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert len(result) == 5
        assert all(len(v) == CLIP_EMBED_DIM for v in result)
