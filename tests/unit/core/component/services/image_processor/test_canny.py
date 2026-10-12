"""Tests for the image-processor OpenCV Canny edge-detection method."""

import pytest

from unittest.mock import AsyncMock, MagicMock
from PIL import Image as PILImage, ImageDraw

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.image_processor.drivers.opencv import OpenCvImageProcessorAction
from mindor.dsl.schema.action.impl.image_processor.impl.opencv import (
    OpenCvImageProcessorCannyActionConfig,
    OpenCvImageProcessorActionMethod,
)

cv2 = pytest.importorskip("cv2")


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_context(image):
    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

    async def render_variable(value, scope=None, skip_decode=False):
        return value

    async def render_scalar(value, cast, default=None):
        if value is None:
            return default
        return cast(value)

    async def render_image(value):
        return image

    context.render_variable = AsyncMock(side_effect=render_variable)
    context.render_scalar = AsyncMock(side_effect=render_scalar)
    context.render_image = AsyncMock(side_effect=render_image)
    context.register_source = MagicMock()
    return context


def _rect_on_black(size=(64, 64), rect_box=(16, 16, 48, 48)):
    image = PILImage.new("RGB", size, (0, 0, 0))
    ImageDraw.Draw(image).rectangle(rect_box, fill=(255, 255, 255))
    return image


class TestCanny:
    @pytest.mark.anyio
    async def test_detects_rectangle_edges(self):
        image = _rect_on_black()
        config = OpenCvImageProcessorCannyActionConfig(
            method=OpenCvImageProcessorActionMethod.CANNY,
            image="${input.image}",
            low_threshold=100,
            high_threshold=200,
        )
        action = OpenCvImageProcessorAction(config)
        result = await action.run(_make_context(image))

        assert isinstance(result, PILImage.Image)
        assert result.mode == "L"
        assert result.size == image.size

        # Canny produces thin edges; sample a small band around each rectangle side.
        def _any_bright(xs, ys):
            return any(result.getpixel((x, y)) > 0 for x in xs for y in ys)

        assert _any_bright(range(14, 18), range(28, 36))   # left edge
        assert _any_bright(range(46, 50), range(28, 36))   # right edge
        assert _any_bright(range(28, 36), range(14, 18))   # top edge
        assert _any_bright(range(28, 36), range(46, 50))   # bottom edge
        assert result.getpixel((32, 32)) == 0              # interior stays dark

    @pytest.mark.anyio
    async def test_rejects_inverted_thresholds(self):
        config = OpenCvImageProcessorCannyActionConfig(
            method=OpenCvImageProcessorActionMethod.CANNY,
            image="${input.image}",
            low_threshold=200,
            high_threshold=100,
        )
        action = OpenCvImageProcessorAction(config)

        with pytest.raises(ValueError, match="low_threshold.*high_threshold"):
            await action.run(_make_context(_rect_on_black()))

    @pytest.mark.anyio
    async def test_rejects_negative_threshold(self):
        config = OpenCvImageProcessorCannyActionConfig(
            method=OpenCvImageProcessorActionMethod.CANNY,
            image="${input.image}",
            low_threshold=-1,
            high_threshold=100,
        )
        action = OpenCvImageProcessorAction(config)

        with pytest.raises(ValueError, match="non-negative"):
            await action.run(_make_context(_rect_on_black()))
