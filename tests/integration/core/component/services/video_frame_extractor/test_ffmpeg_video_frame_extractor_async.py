"""Async / non-blocking tests for the FFmpeg video-frame-extractor driver.

Verifies:
  - `Action.run(context)` yields the event loop while ffmpeg decodes frames.
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
  - Streaming path completes without stalling the loop.
  - Batch input processes each video.
  - A CancellationToken mid-run halts extraction promptly.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_frame_extractor.base import (
    VideoFrameExtractorService,
)
from mindor.core.component.services.video_frame_extractor.drivers.ffmpeg import (
    FFmpegVideoFrameExtractorAction,
    FFmpegVideoFrameExtractorService,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig

from tests.async_helpers import assert_does_not_block, collect_async


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """~3s @ 30fps → ~90 frames — enough wall-time for the ticker to see progress."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=30",
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
                "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
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
        if isinstance(cast, str):
            from mindor.core.foundation.variable.time import parse_time
            from mindor.core.foundation.variable.size import parse_size
            from mindor.core.foundation.variable.decimal import parse_decimal
            from mindor.core.foundation.variable.color import parse_color
            parsers = {
                "time": parse_time,
                "size": parse_size,
                "decimal": parse_decimal,
                "color": parse_color,
            }
            return parsers[cast](value)
        return cast(value)

    ctx.render_scalar = AsyncMock(side_effect=render_scalar)
    return ctx


def _make_config(video, **kwargs) -> VideoFrameExtractorActionConfig:
    return VideoFrameExtractorActionConfig(video=video, **kwargs)


def _assert_frame(item: Any) -> None:
    assert isinstance(item, dict)
    assert "image" in item and isinstance(item["image"], PILImage.Image)
    assert "timestamp" in item


@ffmpeg_required
class TestFFmpegVideoFrameExtractorAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self, sample_video):
        """Collect path: ffmpeg decodes ~90 frames — the ticker must keep firing."""
        action = FFmpegVideoFrameExtractorAction(_make_config(sample_video))
        ctx = _make_context()

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) > 0
        for f in result:
            _assert_frame(f)

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_video):
        sig = inspect.signature(FFmpegVideoFrameExtractorService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        service = FFmpegVideoFrameExtractorService.__new__(FFmpegVideoFrameExtractorService)
        VideoFrameExtractorService.__init__(service, "vfe", MagicMock(), False)

        ctx = _make_context()
        config = _make_config(sample_video)

        result = await service._run(config, ctx)
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.anyio
    async def test_streaming_path_does_not_block(self, sample_video):
        """Streaming path yields frames incrementally — should also keep the loop free."""
        action = FFmpegVideoFrameExtractorAction(_make_config(sample_video, streaming=True))
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
        for f in frames:
            _assert_frame(f)

    @pytest.mark.anyio
    async def test_batch_input_processes_each(self, sample_videos):
        """List input returns List[List[frame]]."""
        action = FFmpegVideoFrameExtractorAction(_make_config(sample_videos))
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

    @pytest.mark.anyio
    async def test_cancellation_token_stops_extraction_promptly(self, tmp_path):
        """Firing the cancellation token mid-run must abort ffmpeg before natural EOF.

        Note: exercises the `_watch_cancellation` polling watcher installed on
        `_collect_frames` — token → `process_task.cancel()` → `kill_process(ffmpeg)`.
        A wall-clock ceiling below the ffmpeg no-cancel time verifies the abort worked.
        """
        # Long enough that extraction to PNGs without cancellation takes many
        # seconds; the wall-clock assertion below will fail if the token is ignored.
        long_source = str(tmp_path / "long.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=duration=30:size=1280x720:rate=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                long_source,
            ],
            check=True, capture_output=True,
        )

        token = CancellationToken()
        ctx = _make_context(cancellation_token=token)
        action = FFmpegVideoFrameExtractorAction(_make_config(long_source))

        run_task = asyncio.create_task(action.run(ctx))
        await asyncio.sleep(0.3)
        token.cancel(reason="test")

        started = time.monotonic()
        with pytest.raises((asyncio.CancelledError, RuntimeError)):
            await run_task
        elapsed = time.monotonic() - started

        # If the token were ignored, extraction of 900 720p frames to PNG would
        # take many tens of seconds. A tight ceiling here catches a regression.
        assert elapsed < 10.0, f"Cancellation took too long: {elapsed:.2f}s"
