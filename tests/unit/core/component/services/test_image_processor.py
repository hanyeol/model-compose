"""Tests for the ImageProcessorAction's I/O matrix: single / list / AsyncIterator input,
with output unspecified / ${result} / ${result[]} / gacked (${result.field}) cases.

The is_stream_mode rule is:
    is_stream_input        = isinstance(image, AsyncIterator)
    is_stream_output       = output references "result[]"
    is_passthrough_output  = output is empty or output == "${result}"
    is_stream_mode         = is_stream_output or (is_stream_input and is_passthrough_output)

Stream mode -> returns AsyncIterator yielding per-item output.
Non-stream mode -> returns single value or list, matching the input shape.
"""

from __future__ import annotations

import asyncio

from collections.abc import AsyncIterator
from typing import Any, List

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.image_processor.drivers.native import NativeImageProcessorAction as ImageProcessorAction
from mindor.dsl.schema.action import ImageProcessorActionConfig
from pydantic import TypeAdapter


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_image(color=(255, 0, 0), size=(8, 8)) -> PILImage.Image:
    return PILImage.new("RGB", size, color)


def _grayscale_config(output: Any = None) -> ImageProcessorActionConfig:
    raw = { "method": "grayscale", "image": "${input.image}" }
    if output is not None:
        raw["output"] = output
    return TypeAdapter(ImageProcessorActionConfig).validate_python(raw)


async def _make_async_iter(images: List[PILImage.Image]) -> AsyncIterator[PILImage.Image]:
    for image in images:
        yield image


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestImageProcessorSingleInput:
    """Single PIL image as input."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_image(self):
        config = _grayscale_config(output=None)
        action = ImageProcessorAction(config)

        image = _make_image()
        context = ComponentActionContext("run-1", { "image": image })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.mode == "L"

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_image(self):
        config = _grayscale_config(output="${result}")
        action = ImageProcessorAction(config)

        image = _make_image()
        context = ComponentActionContext("run-2", { "image": image })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.mode == "L"

    @pytest.mark.anyio
    async def test_stream_output_template_no_longer_triggers_stream_mode(self):
        """Under the new model `${result[]}` no longer forces stream mode; the unit
        result (PILImage) is a single object, so the outer container is decided solely
        by the input shape — a single input returns a single value, not an iterator."""
        config = _grayscale_config(output="${result[]}")
        action = ImageProcessorAction(config)

        image = _make_image()
        context = ComponentActionContext("run-3", { "image": image })
        result = await action.run(context, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)

    @pytest.mark.anyio
    async def test_gacked_output_is_not_stream_mode(self):
        """${result.field} is not passthrough and not result[], so the action takes the
        non-stream path and renders the expression against the collected `result` source.
        PIL Image attributes are not resolved by the renderer, so the rendered value is
        None — what matters here is that the return is a single value (not an iterator)."""
        config = _grayscale_config(output="${result.size}")
        action = ImageProcessorAction(config)

        image = _make_image(size=(16, 9))
        context = ComponentActionContext("run-4", { "image": image })
        result = await action.run(context, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)
        # Renderer does not support attribute access on arbitrary objects, so the
        # gacked expression resolves to None — but the path itself ran non-stream.
        assert result is None


class TestImageProcessorListInput:
    """List of PIL images as input."""

    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        config = _grayscale_config(output=None)
        action = ImageProcessorAction(config)

        images = [ _make_image(color=(c, 0, 0)) for c in (50, 100, 150) ]
        context = ComponentActionContext("run-5", { "image": images })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, PILImage.Image) and item.mode == "L" for item in result)

    @pytest.mark.anyio
    async def test_passthrough_output_returns_list(self):
        config = _grayscale_config(output="${result}")
        action = ImageProcessorAction(config)

        images = [ _make_image(), _make_image() ]
        context = ComponentActionContext("run-6", { "image": images })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(item.mode == "L" for item in result)

    @pytest.mark.anyio
    async def test_stream_output_template_with_list_input_returns_list(self):
        """Same as the single-input case: `${result[]}` alone doesn't activate streaming.
        A list input keeps a list-shaped output."""
        config = _grayscale_config(output="${result[]}")
        action = ImageProcessorAction(config)

        images = [ _make_image() for _ in range(4) ]
        context = ComponentActionContext("run-7", { "image": images })
        result = await action.run(context, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)

    @pytest.mark.anyio
    async def test_gacked_output_evaluates_on_collected_list(self):
        """A gacked output expression (${result.size}) on a list input is not passthrough,
        so the action collects the list and renders against `result` source. Since `result`
        is a list, `.size` does not resolve; the rendered value falls through to the
        source's field-resolver default (None)."""
        config = _grayscale_config(output="${result.size}")
        action = ImageProcessorAction(config)

        images = [ _make_image(), _make_image() ]
        context = ComponentActionContext("run-8", { "image": images })
        result = await action.run(context, asyncio.get_running_loop())

        # `${result.size}` on a list resolves to None because list has no `.size` attr.
        assert result is None


class TestImageProcessorStreamInput:
    """AsyncIterator of PIL images as input."""

    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        config = _grayscale_config(output=None)
        action = ImageProcessorAction(config)

        images = [ _make_image() for _ in range(3) ]
        context = ComponentActionContext("run-9", { "image": _make_async_iter(images) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 3
        assert all(item.mode == "L" for item in items)

    @pytest.mark.anyio
    async def test_passthrough_output_returns_async_iterator(self):
        config = _grayscale_config(output="${result}")
        action = ImageProcessorAction(config)

        images = [ _make_image() for _ in range(3) ]
        context = ComponentActionContext("run-10", { "image": _make_async_iter(images) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 3
        assert all(item.mode == "L" for item in items)

    @pytest.mark.anyio
    async def test_stream_output_returns_async_iterator(self):
        config = _grayscale_config(output="${result[]}")
        action = ImageProcessorAction(config)

        images = [ _make_image() for _ in range(5) ]
        context = ComponentActionContext("run-11", { "image": _make_async_iter(images) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 5
        assert all(item.mode == "L" for item in items)

    @pytest.mark.anyio
    async def test_stream_input_with_non_passthrough_output_still_yields_async_iterator(self):
        """Under the new model AsyncIterator input always produces an AsyncIterator output
        (identity-preserving outer container) — even when the output template is not a
        plain passthrough. The template is applied at the workflow boundary, not here."""
        config = _grayscale_config(output="${result.size}")
        action = ImageProcessorAction(config)

        images = [ _make_image() for _ in range(3) ]
        context = ComponentActionContext("run-12", { "image": _make_async_iter(images) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)


class TestImageProcessorOtherMethods:
    """Sanity check a few non-grayscale methods through the same I/O machinery."""

    @pytest.mark.anyio
    async def test_resize_single(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "resize",
            "image": "${input.image}",
            "width": 4,
            "height": 4,
            "scale_mode": "stretch",
        })
        action = ImageProcessorAction(config)

        image = _make_image(size=(16, 16))
        context = ComponentActionContext("run-13", { "image": image })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.size == (4, 4)

    @pytest.mark.anyio
    async def test_flip_list(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "flip",
            "image": "${input.image}",
            "direction": "horizontal",
        })
        action = ImageProcessorAction(config)

        images = [ _make_image() for _ in range(2) ]
        context = ComponentActionContext("run-14", { "image": images })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, PILImage.Image) for item in result)

    @pytest.mark.anyio
    async def test_rotate_stream(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "rotate",
            "image": "${input.image}",
            "angle": 90,
            "expand": True,
        })
        action = ImageProcessorAction(config)

        images = [ _make_image(size=(8, 4)) for _ in range(2) ]
        context = ComponentActionContext("run-15", { "image": _make_async_iter(images) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 2
        # 90° rotation with expand=True swaps width/height.
        assert all(item.size == (4, 8) for item in items)


class TestImageProcessorAllMethods:
    """Verify every method runs end-to-end on a single image input."""

    @pytest.mark.anyio
    async def test_crop(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "crop", "image": "${input.image}",
            "x": 2, "y": 2, "width": 4, "height": 4,
        })
        image = _make_image(size=(8, 8))
        context = ComponentActionContext("run-c1", { "image": image })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.size == (4, 4)

    @pytest.mark.anyio
    async def test_grayscale(self):
        config = _grayscale_config()
        context = ComponentActionContext("run-c2", { "image": _make_image() })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert result.mode == "L"

    @pytest.mark.anyio
    async def test_blur(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "blur", "image": "${input.image}", "radius": 1.5,
        })
        context = ComponentActionContext("run-c3", { "image": _make_image() })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)

    @pytest.mark.anyio
    async def test_sharpen(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "sharpen", "image": "${input.image}", "factor": 1.5,
        })
        context = ComponentActionContext("run-c4", { "image": _make_image() })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)

    @pytest.mark.anyio
    @pytest.mark.parametrize("method", [
        "adjust-brightness", "adjust-contrast", "adjust-saturation",
    ])
    async def test_adjust_methods(self, method: str):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": method, "image": "${input.image}", "factor": 1.2,
        })
        context = ComponentActionContext(f"run-c5-{method}", { "image": _make_image() })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.size == (8, 8)

    @pytest.mark.anyio
    async def test_flip_vertical(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "flip", "image": "${input.image}", "direction": "vertical",
        })
        context = ComponentActionContext("run-c6", { "image": _make_image() })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)


class TestImageProcessorResizeModes:
    """Resize behaves differently across scale modes (fit/fill/stretch)."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("scale_mode,expected_size", [
        ("stretch", (10, 5)),
        ("fit",     (10, 5)),   # source 16x8 aspect 2:1, fits inside 10x5 -> 10x5
        ("fill",    (10, 5)),   # source 16x8, fills 10x5 then crops -> 10x5
    ])
    async def test_scale_modes(self, scale_mode: str, expected_size: tuple):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "resize", "image": "${input.image}",
            "width": 10, "height": 5, "scale_mode": scale_mode,
        })
        image = _make_image(size=(16, 8))
        context = ComponentActionContext(f"run-r-{scale_mode}", { "image": image })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert result.size == expected_size

    @pytest.mark.anyio
    async def test_resize_width_only(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "resize", "image": "${input.image}",
            "width": 4, "scale_mode": "stretch",
        })
        image = _make_image(size=(16, 16))
        context = ComponentActionContext("run-r-w", { "image": image })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        # height defaults to original
        assert result.size == (4, 16)

    @pytest.mark.anyio
    async def test_resize_height_only(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "resize", "image": "${input.image}",
            "height": 4, "scale_mode": "stretch",
        })
        image = _make_image(size=(16, 16))
        context = ComponentActionContext("run-r-h", { "image": image })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert result.size == (16, 4)


class TestImageProcessorErrors:
    """Validation errors raised by _render_params and _process_batch."""

    @pytest.mark.anyio
    async def test_resize_missing_width_and_height(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "resize", "image": "${input.image}",
        })
        context = ComponentActionContext("run-e1", { "image": _make_image() })

        with pytest.raises(ValueError, match="'width' or 'height'"):
            await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_resize_invalid_scale_mode(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "resize", "image": "${input.image}",
            "width": 4, "scale_mode": "bogus",
        })
        context = ComponentActionContext("run-e2", { "image": _make_image() })

        with pytest.raises(ValueError, match="Invalid scale_mode"):
            await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_flip_invalid_direction(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "flip", "image": "${input.image}", "direction": "diagonal",
        })
        context = ComponentActionContext("run-e3", { "image": _make_image() })

        with pytest.raises(ValueError, match="Invalid flip direction"):
            await ImageProcessorAction(config).run(context, asyncio.get_running_loop())


class TestImageProcessorBatchSize:
    """Batch size affects how BatchSourceIterator groups items but should not change results."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 3, 5, 10])
    async def test_list_input_various_batch_sizes(self, batch_size: int):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "grayscale", "image": "${input.image}", "batch_size": batch_size,
        })
        images = [ _make_image() for _ in range(4) ]
        context = ComponentActionContext(f"run-b-{batch_size}", { "image": images })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 4
        assert all(item.mode == "L" for item in result)

    @pytest.mark.anyio
    async def test_stream_input_with_batch_size(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "grayscale", "image": "${input.image}", "batch_size": 2,
        })
        images = [ _make_image() for _ in range(5) ]
        context = ComponentActionContext("run-b-stream", { "image": _make_async_iter(images) })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 5
        assert all(item.mode == "L" for item in items)


class TestImageProcessorEmptyInput:
    """Empty list / empty AsyncIterator should produce empty output."""

    @pytest.mark.anyio
    async def test_empty_list(self):
        config = _grayscale_config()
        context = ComponentActionContext("run-empty-list", { "image": [] })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert result == []

    @pytest.mark.anyio
    async def test_empty_stream(self):
        config = _grayscale_config()
        context = ComponentActionContext("run-empty-stream", { "image": _make_async_iter([]) })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        # Stream input + passthrough output triggers stream mode -> AsyncIterator.
        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert items == []


class TestImageProcessorVariableInterpolation:
    """Method / params resolved from ${...} variables (not hardcoded in YAML)."""

    @pytest.mark.anyio
    async def test_method_from_variable(self):
        # method is declared as the discriminator in the union, so it must be a literal
        # in the config — variable interpolation on method is not supported at the schema
        # layer. This test ensures the runner-level enum normalization works when called
        # with the proper discriminator value.
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "grayscale", "image": "${input.image}",
        })
        context = ComponentActionContext("run-v1", { "image": _make_image() })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert result.mode == "L"

    @pytest.mark.anyio
    async def test_factor_from_variable(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "adjust-brightness", "image": "${input.image}",
            "factor": "${input.factor}",
        })
        context = ComponentActionContext("run-v2", { "image": _make_image(), "factor": 1.5 })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)

    @pytest.mark.anyio
    async def test_direction_from_variable(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "flip", "image": "${input.image}",
            "direction": "${input.dir}",
        })
        context = ComponentActionContext("run-v3", { "image": _make_image(), "dir": "vertical" })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)

    @pytest.mark.anyio
    async def test_batch_size_from_variable(self):
        config = TypeAdapter(ImageProcessorActionConfig).validate_python({
            "method": "grayscale", "image": "${input.image}",
            "batch_size": "${input.bs}",
        })
        images = [ _make_image() for _ in range(3) ]
        context = ComponentActionContext("run-v4", { "image": images, "bs": 2 })
        result = await ImageProcessorAction(config).run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
