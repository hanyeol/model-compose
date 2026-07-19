"""Tests for the image-processor concat and merge methods covering horizontal, vertical, grid, and overlay behaviors."""

import asyncio

import pytest

from unittest.mock import AsyncMock, MagicMock
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.image_processor.drivers.native import NativeImageProcessorAction
from mindor.core.foundation.variable.color import parse_color
from mindor.dsl.schema.action import ImageProcessorActionMethod
from mindor.dsl.schema.action.impl.image_processor.impl.native import (
    ImageProcessorConcatActionConfig,
    ImageProcessorMergeActionConfig,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_context(images):
    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

    async def render_variable(value, scope=None, skip_decode=False):
        return value

    async def render_image_array(value):
        return [ images ]

    async def render_color(value, default=None):
        if value is None:
            return default
        return parse_color(value)

    context.render_variable = AsyncMock(side_effect=render_variable)
    context.render_image_array = AsyncMock(side_effect=render_image_array)
    context.render_color = AsyncMock(side_effect=render_color)
    context.register_source = MagicMock()
    return context


def _solid(width, height, color):
    return PILImage.new("RGBA", (width, height), color)


async def _run_action(action, context):
    result = await action.run(context, asyncio.get_running_loop())
    return result[0] if isinstance(result, list) and result else (None if result == [] else result)


class TestConcatHorizontal:
    @pytest.mark.anyio
    async def test_uniform_sizes(self):
        images = [
            _solid(10, 10, (255, 0, 0, 255)),
            _solid(10, 10, (0, 255, 0, 255)),
            _solid(10, 10, (0, 0, 255, 255)),
        ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="horizontal",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (30, 10)
        assert result.getpixel(( 5, 5)) == (255, 0, 0, 255)
        assert result.getpixel((15, 5)) == (0, 255, 0, 255)
        assert result.getpixel((25, 5)) == (0, 0, 255, 255)

    @pytest.mark.anyio
    async def test_with_spacing(self):
        images = [ _solid(10, 10, (255, 0, 0, 255)), _solid(10, 10, (0, 255, 0, 255)) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="horizontal",
            spacing=5,
            background="#ffffffff",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (25, 10)
        assert result.getpixel(( 5, 5)) == (255, 0, 0, 255)
        assert result.getpixel((12, 5)) == (255, 255, 255, 255)
        assert result.getpixel((20, 5)) == (0, 255, 0, 255)

    @pytest.mark.anyio
    async def test_different_heights_centered(self):
        images = [ _solid(10, 20, (255, 0, 0, 255)), _solid(10, 10, (0, 255, 0, 255)) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="horizontal",
            background="#00000000",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (20, 20)
        assert result.getpixel((15, 0))  == (0, 0, 0, 0)
        assert result.getpixel((15, 10)) == (0, 255, 0, 255)


class TestConcatVertical:
    @pytest.mark.anyio
    async def test_uniform_sizes(self):
        images = [
            _solid(10, 10, (255, 0, 0, 255)),
            _solid(10, 10, (0, 255, 0, 255)),
            _solid(10, 10, (0, 0, 255, 255)),
        ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="vertical",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (10, 30)
        assert result.getpixel((5,  5)) == (255, 0, 0, 255)
        assert result.getpixel((5, 15)) == (0, 255, 0, 255)
        assert result.getpixel((5, 25)) == (0, 0, 255, 255)

    @pytest.mark.anyio
    async def test_with_spacing(self):
        images = [ _solid(10, 10, (255, 0, 0, 255)), _solid(10, 10, (0, 255, 0, 255)) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="vertical",
            spacing=4,
            background="#ffffffff",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (10, 24)
        assert result.getpixel((5,  5)) == (255, 0, 0, 255)
        assert result.getpixel((5, 12)) == (255, 255, 255, 255)
        assert result.getpixel((5, 20)) == (0, 255, 0, 255)


class TestConcatGrid:
    @pytest.mark.anyio
    async def test_auto_grid_square(self):
        images = [ _solid(10, 10, (i * 60, 0, 0, 255)) for i in range(4) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="grid",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (20, 20)

    @pytest.mark.anyio
    async def test_explicit_columns(self):
        images = [ _solid(10, 10, (255, 0, 0, 255)) for _ in range(6) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="grid",
            columns=3,
            spacing=2,
            background="#ffffffff",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (3 * 10 + 2 * 2, 2 * 10 + 1 * 2)

    @pytest.mark.anyio
    async def test_explicit_rows_only(self):
        images = [ _solid(10, 10, (255, 0, 0, 255)) for _ in range(5) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="grid",
            rows=2,
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        # 5 images, 2 rows → 3 columns
        assert result.size == (30, 20)


class TestMerge:
    @pytest.mark.anyio
    async def test_same_size(self):
        images = [
            _solid(20, 20, (255, 0, 0, 255)),
            _solid(20, 20, (0, 255, 0, 128)),
        ]
        config = ImageProcessorMergeActionConfig(
            method=ImageProcessorActionMethod.MERGE,
            image="${input.images}",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (20, 20)
        red, green, blue, alpha = result.getpixel((10, 10))
        # green half-alpha on top of red → roughly mixed
        assert green > 100
        assert red < 200
        assert alpha == 255

    @pytest.mark.anyio
    async def test_different_sizes_centered(self):
        big   = _solid(30, 30, (255, 0, 0, 255))
        small = _solid(10, 10, (0, 255, 0, 255))
        config = ImageProcessorMergeActionConfig(
            method=ImageProcessorActionMethod.MERGE,
            image="${input.images}",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context([ big, small ]))

        assert result.size == (30, 30)
        # small is centered, so the middle pixel must be green
        assert result.getpixel((15, 15)) == (0, 255, 0, 255)
        # outer area must be red (only big image covers it)
        assert result.getpixel((2, 2))   == (255, 0, 0, 255)


class TestConcatEdgeCases:
    @pytest.mark.anyio
    async def test_single_image_passthrough(self):
        images = [ _solid(15, 15, (10, 20, 30, 255)) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="horizontal",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (15, 15)

    @pytest.mark.anyio
    async def test_empty_input_returns_none(self):
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="horizontal",
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context([]))

        assert result is None

    @pytest.mark.anyio
    async def test_rgb_tuple_background(self):
        images = [ _solid(10, 10, (255, 0, 0, 255)), _solid(10, 20, (0, 255, 0, 255)) ]
        config = ImageProcessorConcatActionConfig(
            method=ImageProcessorActionMethod.CONCAT,
            image="${input.images}",
            mode="horizontal",
            background=[ 50, 100, 150 ],
        )
        action = NativeImageProcessorAction(config)
        result = await _run_action(action, _make_context(images))

        assert result.size == (20, 20)
        # padding area above first image is background
        assert result.getpixel((5, 0)) == (50, 100, 150, 255)
