"""Async / non-blocking tests for the OpenCV video-frame-extractor driver.

Verifies:
  - `Action.run(context)` yields the event loop while cv2 decodes frames on a
    background executor (CPU-bound sync work must be offloaded via
    `_run_in_executor`, not block the loop).
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
  - Streaming path completes without stalling the loop.
  - Batch input processes each video.
"""

from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import tempfile
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig

from tests.async_helpers import assert_does_not_block, collect_async


cv2 = pytest.importorskip("cv2", reason="opencv-python not installed")

# Import driver only after cv2 is confirmed importable.
from mindor.core.component.services.video_frame_extractor.base import (
    VideoFrameExtractorService,
)
from mindor.core.component.services.video_frame_extractor.drivers.opencv import (
    OpenCVVideoFrameExtractorAction,
    OpenCVVideoFrameExtractorService,
)

from PIL import Image as PILImage


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """~2s testsrc @ 30fps → ~60 frames. Enough wall time for the ticker."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sample_videos(sample_video):
    paths: List[str] = []
    for _ in range(2):
        path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=24",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                path,
            ],
            check=True, capture_output=True,
        )
        paths.append(path)
    yield paths
    for p in paths:
        if os.path.exists(p):
            os.unlink(p)


def _media_source(path: str) -> MediaSource:
    return MediaSource(stream=FileStreamResource(path), format="mp4")


def _make_context(resolved_video: Any = None, *, cancellation_token=None):
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = cancellation_token
    ctx.register_source = MagicMock()

    async def render_variable(value, **kwargs):
        return value

    async def render_video(value):
        if resolved_video is not None:
            return resolved_video
        return MediaSource(stream=FileStreamResource(value), format="mp4")

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)

    async def render_scalar(value, cast, default=None):
        if value is None:
            return default
        return cast(value)

    async def render_time(value, default=None):
        if value is None:
            return default
        from mindor.core.foundation.variable.time import parse_time
        return parse_time(value)

    ctx.render_scalar = AsyncMock(side_effect=render_scalar)
    ctx.render_time = AsyncMock(side_effect=render_time)
    return ctx


def _make_config(video, **kwargs) -> VideoFrameExtractorActionConfig:
    return VideoFrameExtractorActionConfig(video=video, **kwargs)


def _assert_frame(item: Any) -> None:
    assert isinstance(item, dict)
    assert "image" in item and isinstance(item["image"], PILImage.Image)
    assert "timestamp" in item


@ffmpeg_required
class TestOpenCVVideoFrameExtractorAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self, sample_video):
        """cv2.VideoCapture + frame decode is sync CPU work — must be offloaded."""
        action = OpenCVVideoFrameExtractorAction(_make_config(sample_video))
        ctx = _make_context()

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) > 0
        for frame in result:
            _assert_frame(frame)

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_video):
        sig = inspect.signature(OpenCVVideoFrameExtractorService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        service = OpenCVVideoFrameExtractorService.__new__(OpenCVVideoFrameExtractorService)
        VideoFrameExtractorService.__init__(service, "vfe", MagicMock(), False)

        ctx = _make_context()
        config = _make_config(sample_video)

        result = await service._run(config, ctx)
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.anyio
    async def test_streaming_path_does_not_block(self, sample_video):
        """Streaming path uses a SyncGeneratorStreamer — should also keep the loop free."""
        action = OpenCVVideoFrameExtractorAction(_make_config(sample_video, streaming=True))
        ctx = _make_context()

        async def _consume():
            iterator = await action.run(ctx)
            assert isinstance(iterator, StreamChunkIterator)
            return await collect_async(iterator)

        frames = await assert_does_not_block(
            _consume(),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert len(frames) > 0
        for frame in frames:
            _assert_frame(frame)

    @pytest.mark.anyio
    async def test_batch_input_processes_each(self, sample_videos):
        """List input returns List[List[frame]]."""
        action = OpenCVVideoFrameExtractorAction(_make_config(sample_videos))
        ctx = _make_context(resolved_video=[_media_source(p) for p in sample_videos])

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) == len(sample_videos)
        for per_video in result:
            assert isinstance(per_video, list)
            assert len(per_video) > 0
