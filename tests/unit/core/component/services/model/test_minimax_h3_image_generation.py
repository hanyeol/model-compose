"""Runtime tests for the MiniMax-H3-Image custom image-generation driver.

Verifies the shape of ``_prepare_input`` + ``_generate_batch`` across the input
matrix the ``ImageGenerationTaskAction`` base supports (single prompt, list of
prompts, AsyncIterator), and across the two methods (``generate``, ``edit``).

The pipeline is mocked (the real 68 GB checkpoint is out of scope); what is
exercised here is:
  - Input rendering: prompt from context, reference images for ``edit``.
  - ``pipeline_params`` kwargs assembled for each call — ``prompt``, ``image``
    for edit, ``height``/``width``/``min_generation_area``, ``output="images"``.
  - Sol backend wires ``callback_on_step_end`` and calls
    ``processor.begin_steps(_MINIMAX_H3_IMAGE_SAMPLE_STEPS)`` per item;
    ``advance_step`` fires once per denoising step via the callback.
  - Output shape mirrors ``ImageGenerationTaskAction``: single-in/single-out,
    list-in/list-out, AsyncIterator-in/AsyncIterator-out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, List
from unittest.mock import MagicMock

import pytest
from PIL import Image as PILImage
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.image_generation.custom.minimax_h3.base import (
    MinimaxH3ImageGenerationGenerateAction,
    MinimaxH3ImageGenerationEditAction,
    _MINIMAX_H3_IMAGE_SAMPLE_STEPS,
)
from mindor.core.component.services.model.tasks.image_generation.custom.minimax_h3.backends.sol import (
    MinimaxH3SolImageGenerationGenerateAction,
    MinimaxH3SolImageGenerationEditAction,
)
from mindor.dsl.schema.action import (
    MinimaxH3ImageGenerationModelGenerateActionConfig,
    MinimaxH3ImageGenerationModelEditActionConfig,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_image(color=(255, 0, 0), size=(8, 8)) -> PILImage.Image:
    return PILImage.new("RGB", size, color)


async def _aiter(items: List[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


def _generate_config(**overrides) -> MinimaxH3ImageGenerationModelGenerateActionConfig:
    raw = {
        "method":            "generate",
        "prompt":            "${input.prompt}",
        "width":             4096,
        "height":            4096,
        "num_return_images": 1,
        "batch_size":        1,
        **overrides,
    }
    return TypeAdapter(MinimaxH3ImageGenerationModelGenerateActionConfig).validate_python(raw)


def _edit_config(**overrides) -> MinimaxH3ImageGenerationModelEditActionConfig:
    raw = {
        "method":            "edit",
        "prompt":            "${input.prompt}",
        "image":             "${input.image}",
        "width":             4096,
        "height":            4096,
        "num_return_images": 1,
        "batch_size":        1,
        **overrides,
    }
    return TypeAdapter(MinimaxH3ImageGenerationModelEditActionConfig).validate_python(raw)


class _FakePipeline:
    """Captures pipeline call kwargs and returns deterministic PIL image(s).

    Mirrors the shape of ``MiniMaxH3ImageModularPipeline`` just enough for the
    action classes: it is callable, returns an iterable of PIL images, and
    exposes a ``device`` attribute for ``torch.Generator(device=...)``.
    """

    def __init__(self, return_count: int = 1, device: str = "cpu"):
        self.return_count = return_count
        self.device = device
        self.calls: List[dict] = []

    def __call__(self, **kwargs) -> List[PILImage.Image]:
        self.calls.append(kwargs)
        # Simulate 6-step denoising so sol's callback_on_step_end fires.
        callback = kwargs.get("callback_on_step_end")
        if callback is not None:
            for step in range(_MINIMAX_H3_IMAGE_SAMPLE_STEPS):
                callback(self, step, None, {})
        return [ _make_image(color=(step * 40 % 255, 0, 0)) for step in range(self.return_count) ]


# --------------------------------------------------------------------------- #
# Generate: single prompt                                                     #
# --------------------------------------------------------------------------- #

class TestGenerateSinglePrompt:
    @pytest.mark.anyio
    async def test_returns_single_image(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(_generate_config(), pipeline, device=None)

        context = ComponentActionContext("run-1", { "prompt": "an astronaut in a jungle" })
        result = await action.run(context)

        assert isinstance(result, PILImage.Image)
        assert len(pipeline.calls) == 1
        call = pipeline.calls[0]
        assert call["prompt"] == "an astronaut in a jungle"
        assert call["height"] == 4096
        assert call["width"] == 4096
        assert call["min_generation_area"] == 4194304
        assert call["output"] == "images"
        assert "image" not in call
        assert "callback_on_step_end" not in call

    @pytest.mark.anyio
    async def test_seed_builds_torch_generator(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(
            _generate_config(seed=42), pipeline, device=None,
        )

        context = ComponentActionContext("run-seed", { "prompt": "x" })
        await action.run(context)

        import torch
        assert isinstance(pipeline.calls[0]["generator"], torch.Generator)

    @pytest.mark.anyio
    async def test_no_seed_passes_none_generator(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(_generate_config(), pipeline, device=None)

        context = ComponentActionContext("run-noseed", { "prompt": "x" })
        await action.run(context)

        assert pipeline.calls[0]["generator"] is None

    @pytest.mark.anyio
    async def test_dimensions_are_rendered_from_context(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(
            _generate_config(width="${input.w}", height="${input.h}"),
            pipeline, device=None,
        )

        context = ComponentActionContext("run-dim", { "prompt": "x", "w": 5472, "h": 3072 })
        await action.run(context)

        call = pipeline.calls[0]
        assert call["width"] == 5472
        assert call["height"] == 3072

    @pytest.mark.anyio
    async def test_min_generation_area_override(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(
            _generate_config(params={ "min_generation_area": 1048576 }),
            pipeline, device=None,
        )

        context = ComponentActionContext("run-area", { "prompt": "x" })
        await action.run(context)

        assert pipeline.calls[0]["min_generation_area"] == 1048576


# --------------------------------------------------------------------------- #
# Generate: list of prompts (batch)                                           #
# --------------------------------------------------------------------------- #

class TestGenerateListPrompts:
    @pytest.mark.anyio
    async def test_list_input_returns_list_of_images(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(_generate_config(), pipeline, device=None)

        prompts = [ "a", "b", "c" ]
        context = ComponentActionContext("run-list", { "prompt": prompts })
        result = await action.run(context)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, PILImage.Image) for item in result)

        # Each prompt should produce its own pipeline call (batch_size=1).
        assert len(pipeline.calls) == 3
        assert [ call["prompt"] for call in pipeline.calls ] == prompts

    @pytest.mark.anyio
    async def test_batch_size_groups_prompts_but_each_item_still_calls_pipeline(self):
        """The action iterates batch items one-by-one inside the executor closure,
        so batch_size affects BatchSourceIterator chunking but not the per-item
        pipeline call count."""
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(
            _generate_config(batch_size=2), pipeline, device=None,
        )

        prompts = [ "a", "b", "c", "d" ]
        context = ComponentActionContext("run-batch", { "prompt": prompts })
        result = await action.run(context)

        assert isinstance(result, list)
        assert len(result) == 4
        assert len(pipeline.calls) == 4

    @pytest.mark.anyio
    async def test_pipeline_returning_multiple_images_per_call_extends_results(self):
        """When num_return_images > 1 and the pipeline returns N images per call,
        all images flow into the results list via `results.extend(list(output))`."""
        pipeline = _FakePipeline(return_count=3)
        action = MinimaxH3ImageGenerationGenerateAction(
            _generate_config(num_return_images=3), pipeline, device=None,
        )

        context = ComponentActionContext("run-multi", { "prompt": [ "a", "b" ] })
        result = await action.run(context)

        assert isinstance(result, list)
        assert len(result) == 6  # 2 prompts * 3 images/call


# --------------------------------------------------------------------------- #
# Generate: AsyncIterator (streaming)                                         #
# --------------------------------------------------------------------------- #

class TestGenerateStreaming:
    @pytest.mark.anyio
    async def test_async_iterator_input_yields_async_iterator_output(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationGenerateAction(_generate_config(), pipeline, device=None)

        prompts = _aiter([ "p1", "p2", "p3" ])
        context = ComponentActionContext("run-stream", { "prompt": prompts })
        result = await action.run(context)

        assert isinstance(result, AsyncIterator)
        collected = await _collect(result)
        assert len(collected) == 3
        assert all(isinstance(item, PILImage.Image) for item in collected)
        assert [ call["prompt"] for call in pipeline.calls ] == [ "p1", "p2", "p3" ]


# --------------------------------------------------------------------------- #
# Edit: single prompt + single reference image                                #
# --------------------------------------------------------------------------- #

class TestEditSingleReference:
    @pytest.mark.anyio
    async def test_single_prompt_single_ref_image(self):
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationEditAction(_edit_config(), pipeline, device=None)

        reference = _make_image()
        context = ComponentActionContext("run-edit-1", {
            "prompt": "remove the headphones",
            "image":  reference,
        })
        result = await action.run(context)

        assert isinstance(result, PILImage.Image)
        assert len(pipeline.calls) == 1
        call = pipeline.calls[0]
        assert call["prompt"] == "remove the headphones"
        # single_as_array=True in _prepare_input makes `image` always a list,
        # then the _generate_batch wraps it again — upstream expects a list.
        assert isinstance(call["image"], list)
        assert all(isinstance(item, PILImage.Image) for item in call["image"])

    @pytest.mark.anyio
    async def test_prompt_single_multiple_ref_images(self):
        """Edit accepts up to 16 reference images; a list-of-PIL input must land
        on the pipeline as a flat list (not a nested list), since the user passed
        the list as a single-item batch's references."""
        pipeline = _FakePipeline()
        action = MinimaxH3ImageGenerationEditAction(_edit_config(), pipeline, device=None)

        refs = [ _make_image(color=(c, 0, 0)) for c in (50, 100, 150, 200) ]
        context = ComponentActionContext("run-edit-multi", {
            "prompt": "keep <Picture 1>, replace <Picture 2>, blend <Picture 3>, <Picture 4>",
            "image":  refs,
        })
        result = await action.run(context)

        assert isinstance(result, PILImage.Image)
        assert len(pipeline.calls) == 1
        call = pipeline.calls[0]
        assert isinstance(call["image"], list)
        assert len(call["image"]) == 4


# --------------------------------------------------------------------------- #
# Sol backend: callback wiring + step-counter calls                           #
# --------------------------------------------------------------------------- #

class TestSolBackendStepCounter:
    @pytest.mark.anyio
    async def test_generate_invokes_begin_steps_and_advance_step_per_item(self):
        pipeline = _FakePipeline()
        processor = MagicMock()
        action = MinimaxH3SolImageGenerationGenerateAction(
            _generate_config(),
            pipeline,
            device=None,
            sol_attn_processor=processor,
        )

        context = ComponentActionContext("run-sol-gen", { "prompt": [ "a", "b" ] })
        await action.run(context)

        # One begin_steps per item, called with the fixed sample-step constant.
        assert processor.begin_steps.call_count == 2
        processor.begin_steps.assert_called_with(_MINIMAX_H3_IMAGE_SAMPLE_STEPS)

        # advance_step fires once per denoising step per item -> 6 * 2 = 12.
        assert processor.advance_step.call_count == 2 * _MINIMAX_H3_IMAGE_SAMPLE_STEPS

        # Every pipeline call includes the callback.
        assert all("callback_on_step_end" in call for call in pipeline.calls)
        assert len(pipeline.calls) == 2

    @pytest.mark.anyio
    async def test_edit_invokes_begin_steps_and_advance_step_per_item(self):
        pipeline = _FakePipeline()
        processor = MagicMock()
        action = MinimaxH3SolImageGenerationEditAction(
            _edit_config(),
            pipeline,
            device=None,
            sol_attn_processor=processor,
        )

        context = ComponentActionContext("run-sol-edit", {
            "prompt": "x",
            "image":  _make_image(),
        })
        await action.run(context)

        processor.begin_steps.assert_called_once_with(_MINIMAX_H3_IMAGE_SAMPLE_STEPS)
        assert processor.advance_step.call_count == _MINIMAX_H3_IMAGE_SAMPLE_STEPS
        assert pipeline.calls[0]["image"] is not None
        assert "callback_on_step_end" in pipeline.calls[0]
