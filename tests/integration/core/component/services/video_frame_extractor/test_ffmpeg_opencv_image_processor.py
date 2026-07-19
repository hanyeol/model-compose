"""Integration tests: feed video_frame_extractor output into image_processor.

Each test runs against both driver backends (opencv, ffmpeg). The extractor
always operates in collect mode and returns ``List[Dict]`` of frames; tests
exercise the matrix of processor input shape (single, list, async iterator)
and processor output shape (passthrough, stream).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any, Callable, List

import pytest
from PIL import Image as PILImage
from pydantic import TypeAdapter
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.image_processor.drivers.native import NativeImageProcessorAction as ImageProcessorAction
from mindor.core.component.services.video_frame_extractor.drivers.common import VideoFrameExtractorAction
from mindor.core.component.services.video_frame_extractor.drivers.ffmpeg import FFmpegVideoFrameExtractorAction
from mindor.core.component.services.video_frame_extractor.drivers.opencv import OpenCVVideoFrameExtractorAction
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.dsl.schema.action import ImageProcessorActionConfig, VideoFrameExtractorActionConfig


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"),
    reason="ffmpeg not installed (needed for sample video generation and ffmpeg driver)",
)


# ---- Fixtures ----


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """6-frame test video at fps=10, generated with ffmpeg testsrc."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=0.6:size=32x24:rate=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        path,
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"ffmpeg failed to generate test video: {e.stderr.decode('utf-8', errors='replace')}")

    yield path

    if os.path.exists(path):
        os.unlink(path)


def _has_opencv() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


DRIVERS: List[Any] = []
if _has_opencv():
    DRIVERS.append(pytest.param(OpenCVVideoFrameExtractorAction, id="opencv"))
DRIVERS.append(pytest.param(FFmpegVideoFrameExtractorAction, id="ffmpeg"))


# ---- Helpers ----


def make_extractor_context(video_path: str):
    """Mock context that resolves render_video to a FileStreamResource MediaSource."""
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    ctx.register_source = MagicMock()

    async def render_variable(value, **kwargs):
        return value

    async def render_video(value):
        return MediaSource(stream=FileStreamResource(value), format="mp4")

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


def make_processor_context(input_payload: Any, stream_output: bool = False):
    """Mock context for image_processor.

    - ``input_payload`` is bound to ``${input.image}`` references.
    - ``stream_output`` toggles whether ``${result[]}`` produces an async iterator.
    """
    sources: dict[str, Any] = {}

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None

    def register_source(key: str, value: Any) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        # Mimic just enough of the renderer to resolve ${input.image}, ${result}, ${result[]}.
        if isinstance(value, str):
            if value == "${input.image}":
                return input_payload
            if value == "${result}":
                return sources.get("result")
            if value == "${result[]}":
                # When set explicitly as the output, signal pass-through of streamed items.
                return sources.get("result[]")
        return value

    async def render_image(value):
        rendered = await render_variable(value)
        # Pass through PIL Images, lists of them, and async iterators unchanged.
        return rendered

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_image = AsyncMock(side_effect=render_image)
    return ctx


def _extractor_config(video: str, output: Any = None, **kwargs) -> VideoFrameExtractorActionConfig:
    raw = { "video": video, **kwargs }
    if output is not None:
        raw["output"] = output
    return VideoFrameExtractorActionConfig(**raw)


def _processor_config(method: str = "grayscale", output: Any = None, **kwargs) -> ImageProcessorActionConfig:
    raw = { "method": method, "image": "${input.image}", **kwargs }
    if output is not None:
        raw["output"] = output
    return TypeAdapter(ImageProcessorActionConfig).validate_python(raw)


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


def _async_iter(items: List[Any]) -> AsyncIterator[Any]:
    async def _gen():
        for item in items:
            yield item
    return _gen()


# ---- Extractor → list-of-images Processor ----


class TestExtractorToListProcessor:
    """Extractor collect → processor receives list of PIL Images."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_grayscale_list_returns_list(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())

        assert isinstance(ext_result, list)
        assert len(ext_result) == 6

        images = [ frame["image"] for frame in ext_result ]

        proc = ImageProcessorAction(_processor_config(method="grayscale"))
        proc_ctx = make_processor_context(images)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 6
        assert all(isinstance(item, PILImage.Image) and item.mode == "L" for item in result)

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_resize_list_changes_dimensions(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())
        images = [ frame["image"] for frame in ext_result ]

        proc = ImageProcessorAction(_processor_config(method="resize", width=16, height=12, scale_mode="stretch"))
        proc_ctx = make_processor_context(images)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert len(result) == 6
        assert all(item.size == (16, 12) for item in result)

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_rotate_list_changes_orientation(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())
        images = [ frame["image"] for frame in ext_result ]
        original_sizes = [ img.size for img in images ]

        proc = ImageProcessorAction(_processor_config(method="rotate", angle=90, expand=True))
        proc_ctx = make_processor_context(images)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert len(result) == 6
        # 90deg rotation with expand=True swaps dimensions.
        for original, rotated in zip(original_sizes, result):
            assert rotated.size == (original[1], original[0])


# ---- Extractor → single-image Processor ----


class TestExtractorToSingleProcessor:
    """max_frame_count=1 extractor + processor with a single PIL Image."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_single_grayscale(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video, max_frame_count=1)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())

        assert len(ext_result) == 1
        single = ext_result[0]["image"]
        assert isinstance(single, PILImage.Image)

        proc = ImageProcessorAction(_processor_config(method="grayscale"))
        proc_ctx = make_processor_context(single)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.mode == "L"

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_single_resize(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video, max_frame_count=1)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())
        single = ext_result[0]["image"]

        proc = ImageProcessorAction(_processor_config(method="resize", width=8, height=6, scale_mode="stretch"))
        proc_ctx = make_processor_context(single)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert isinstance(result, PILImage.Image)
        assert result.size == (8, 6)


# ---- Extractor → async-iterator Processor ----


class TestExtractorToAsyncIteratorProcessor:
    """Wrap extracted frames in an async iterator and feed to processor."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_async_iterator_grayscale(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())
        images = [ frame["image"] for frame in ext_result ]

        stream_input = _async_iter(images)
        proc = ImageProcessorAction(_processor_config(method="grayscale"))
        proc_ctx = make_processor_context(stream_input)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        # Processor sees an AsyncIterator input and passes it through to its
        # internal handling — result should be an AsyncIterator yielding processed frames.
        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 6
        assert all(item.mode == "L" for item in items)

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_async_iterator_flip(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())
        images = [ frame["image"] for frame in ext_result ]

        stream_input = _async_iter(images)
        proc = ImageProcessorAction(_processor_config(method="flip", direction="horizontal"))
        proc_ctx = make_processor_context(stream_input)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 6
        assert all(isinstance(item, PILImage.Image) for item in items)


# ---- Extractor metadata preservation ----


class TestExtractorMetadata:
    """Frame metadata (timestamp, image) survives until processor consumes it."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_frames_carry_image_and_timestamp(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())

        for frame in ext_result:
            assert "timestamp" in frame
            assert "image" in frame
            assert isinstance(frame["image"], PILImage.Image)

        timestamps = [ frame["timestamp"] for frame in ext_result ]
        assert timestamps == sorted(timestamps)

    @pytest.mark.anyio
    @pytest.mark.parametrize("driver", DRIVERS)
    async def test_frame_interval_propagates_to_processor(self, sample_video, driver):
        ext_cfg = _extractor_config(sample_video, frame_interval=2)
        ext = driver(ext_cfg)
        ext_ctx = make_extractor_context(sample_video)
        ext_result = await ext.run(ext_ctx, asyncio.get_running_loop())

        # 6 source frames / interval 2 → 3 frames downstream.
        assert len(ext_result) == 3
        images = [ frame["image"] for frame in ext_result ]

        proc = ImageProcessorAction(_processor_config(method="grayscale"))
        proc_ctx = make_processor_context(images)
        result = await proc.run(proc_ctx, asyncio.get_running_loop())

        assert len(result) == 3
        assert all(item.mode == "L" for item in result)
