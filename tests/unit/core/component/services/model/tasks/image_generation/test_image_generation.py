"""Tests for the ImageGenerationTaskAction's I/O matrix.

Text-to-image has no token-level streaming (each sample is a single-shot
diffusion run), so the output-shape rule is:

    is_stream_input  = isinstance(prompt, AsyncIterator)
    is_direct_output = output is empty or output == "${result}"

Single-string input returns a single PIL Image. List input returns
List[PIL.Image]. AsyncIterator input returns AsyncIterator[PIL.Image].
Batches are formed via BatchSourceIterator; the fake ``_generate`` records
each batch so the tests can verify boundaries.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, List

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.image_generation.common import ImageGenerationTaskAction
from mindor.dsl.schema.action import SdxlHuggingfaceImageGenerationModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_image(label: str) -> PILImage.Image:
    """A trivial 1x1 image whose ``info['label']`` recovers the prompt.

    Tests use this to correlate output images with the prompts that produced
    them, without doing any real inference.
    """
    img = PILImage.new("RGB", (1, 1), color=(0, 0, 0))
    img.info["label"] = label
    return img


def _label(img: PILImage.Image) -> str:
    assert isinstance(img, PILImage.Image)
    return img.info["label"]


class _FakeImageGenerationAction(ImageGenerationTaskAction):
    """Deterministic ``_generate`` for testing.

    Records batches so tests can assert on batch boundaries; returns one
    fake image per prompt.
    """

    def __init__(self, config: SdxlHuggingfaceImageGenerationModelActionConfig):
        super().__init__(config, device=None)
        self.batches_seen: List[List[str]] = []

    async def _generate(
        self,
        prompts: List[str],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> List[PILImage.Image]:
        self.batches_seen.append(list(prompts))
        return [ _fake_image(p) for p in prompts ]


def _make_config(
    prompt_expr: Any,
    *,
    output: Any = None,
    batch_size: int = 2,
) -> SdxlHuggingfaceImageGenerationModelActionConfig:
    raw: dict = {
        "prompt": prompt_expr,
        "batch_size": batch_size,
    }
    if output is not None:
        raw["output"] = output
    return SdxlHuggingfaceImageGenerationModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _collect(stream) -> list:
    return [ item async for item in stream ]


class TestSingleInput:
    @pytest.mark.anyio
    async def test_no_output_returns_single_image(self):
        action = _FakeImageGenerationAction(_make_config("${input.prompt}"))
        ctx = ComponentActionContext("r-1", { "prompt": "hello" })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, PILImage.Image)
        assert _label(result) == "hello"
        assert action.batches_seen == [ [ "hello" ] ]

    @pytest.mark.anyio
    async def test_literal_prompt_returns_single_image(self):
        action = _FakeImageGenerationAction(_make_config("a cat"))
        ctx = ComponentActionContext("r-2", {})
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, PILImage.Image)
        assert _label(result) == "a cat"


class TestListInput:
    @pytest.mark.anyio
    async def test_returns_list_of_images(self):
        action = _FakeImageGenerationAction(_make_config("${input.prompts}"))
        ctx = ComponentActionContext("r-3", { "prompts": [ "a", "bb", "ccc", "dddd" ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert [ _label(img) for img in result ] == [ "a", "bb", "ccc", "dddd" ]
        # batch_size=2 -> two batches
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc", "dddd" ] ]

    @pytest.mark.anyio
    async def test_uneven_last_batch(self):
        action = _FakeImageGenerationAction(_make_config("${input.prompts}", batch_size=3))
        ctx = ComponentActionContext("r-4", { "prompts": [ "a", "b", "c", "d" ] })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert [ _label(img) for img in result ] == [ "a", "b", "c", "d" ]
        assert action.batches_seen == [ [ "a", "b", "c" ], [ "d" ] ]


class TestStreamInput:
    @pytest.mark.anyio
    async def test_returns_async_iterator(self):
        action = _FakeImageGenerationAction(_make_config("${input.prompts}"))
        stream = _make_async_iter([ "a", "bb", "ccc" ])
        ctx = ComponentActionContext("r-5", { "prompts": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert [ _label(img) for img in items ] == [ "a", "bb", "ccc" ]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc" ] ]

    @pytest.mark.anyio
    async def test_direct_output_returns_async_iterator(self):
        action = _FakeImageGenerationAction(_make_config("${input.prompts}", output="${result}"))
        stream = _make_async_iter([ "a", "bb" ])
        ctx = ComponentActionContext("r-6", { "prompts": stream })
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert [ _label(img) for img in items ] == [ "a", "bb" ]


class TestOutputExpression:
    @pytest.mark.anyio
    async def test_result_reference_returns_direct(self):
        action = _FakeImageGenerationAction(_make_config("hello", output="${result}"))
        ctx = ComponentActionContext("r-7", {})
        loop = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, PILImage.Image)
        assert _label(result) == "hello"
