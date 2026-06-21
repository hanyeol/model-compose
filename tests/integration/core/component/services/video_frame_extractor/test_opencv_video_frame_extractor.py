"""Tests for the OpenCV video-frame-extractor driver.

Verifies the identity-preserving output container rules across the input × streaming matrix:

    | input \\ streaming  | false              | true                          |
    |---------------------|--------------------|-------------------------------|
    | B                   | List[F]            | StreamChunkIterator           |
    | List[B]             | List[List[F]]      | List[StreamChunkIterator]     |
    | AsyncIterator[B]    | AsyncIter[List[F]] | AsyncIter[StreamChunkIterator]|
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any, List

import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_frame_extractor.drivers.opencv import OpenCVVideoFrameExtractorAction
from mindor.core.utils.streaming.iterators import StreamChunkIterator
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.utils.streaming.file import FileStreamResource
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"),
    reason="ffmpeg not installed (needed to generate the sample video)",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_context(resolved_video: Any = None):
    """Mock context.

    `resolved_video` overrides what `render_video` returns regardless of the configured
    `video` field — used for List[B] and AsyncIterator[B] cases where Pydantic would
    otherwise reject non-string inputs at config-construction time.
    """
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.contains_variable_reference = MagicMock(return_value=False)
    ctx.register_source = MagicMock()

    async def render_variable(value, **kwargs):
        return value

    async def render_video(value):
        if resolved_video is not None:
            return resolved_video
        return MediaSource(stream=FileStreamResource(value), format="mp4")

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


def _media_source(path: str) -> MediaSource:
    return MediaSource(stream=FileStreamResource(path), format="mp4")


async def _collect_async(iterable: AsyncIterator[Any]) -> list:
    out = []
    async for item in iterable:
        out.append(item)
    return out


async def _async_media_iter(paths: List[str]) -> AsyncIterator[MediaSource]:
    for path in paths:
        yield _media_source(path)


@pytest.fixture(scope="module")
def sample_video():
    """Generate a small deterministic test video with ffmpeg's `testsrc` source.

    30 frames at fps=10 (duration 3s) of the color test pattern at 64x48.
    """
    try:
        import cv2  # required to run the driver itself
    except ImportError:
        pytest.skip("opencv-python not installed")

    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=64x48:rate=10",
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


@pytest.fixture(scope="module")
def sample_videos(sample_video):
    """Two deterministic test videos. Each produces 10 frames at fps=10."""
    paths: List[str] = []

    for duration_s, rate in [(1, 10), (2, 5)]:  # 10 frames, 10 frames
        path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=64x48:rate={rate}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            path,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            pytest.skip(f"ffmpeg failed: {e.stderr.decode('utf-8', errors='replace')}")
        paths.append(path)

    yield paths

    for p in paths:
        if os.path.exists(p):
            os.unlink(p)


def make_config(video, **kwargs):
    return VideoFrameExtractorActionConfig(video=video, **kwargs)


def _assert_frame(item: Any) -> None:
    assert isinstance(item, dict)
    assert "image" in item and isinstance(item["image"], PILImage.Image)
    assert "timestamp" in item


class TestOpenCVCollectMode:
    """OpenCV driver returns a List[Dict] of frames after collecting them."""

    @pytest.mark.anyio
    async def test_extracts_all_frames_by_default(self, sample_video):
        config = make_config(sample_video)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert len(result) == 30

    @pytest.mark.anyio
    async def test_frame_interval_skips_frames(self, sample_video):
        config = make_config(sample_video, frame_interval=2)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert len(result) == 15

    @pytest.mark.anyio
    async def test_max_frame_count_limits_output(self, sample_video):
        config = make_config(sample_video, max_frame_count=5)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert len(result) == 5

    @pytest.mark.anyio
    async def test_each_frame_has_expected_keys(self, sample_video):
        config = make_config(sample_video, max_frame_count=3)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        for chunk in result:
            assert "timestamp" in chunk
            assert "image" in chunk
            assert isinstance(chunk["image"], PILImage.Image)

    @pytest.mark.anyio
    async def test_timestamps_respect_interval(self, sample_video):
        """At fps=10 with frame_interval=3, timestamps step by 0.3s."""
        config = make_config(sample_video, frame_interval=3, max_frame_count=5)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        timestamps = [chunk["timestamp"] for chunk in result]
        assert timestamps == [pytest.approx(t, abs=0.05) for t in [0.0, 0.3, 0.6, 0.9, 1.2]]

    @pytest.mark.anyio
    async def test_timestamps_match_frame_rate(self, sample_video):
        """OpenCV computes timestamp from frame index / fps; fps=10 gives 0.0, 0.1, 0.2..."""
        config = make_config(sample_video, max_frame_count=3)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        timestamps = [chunk["timestamp"] for chunk in result]
        assert timestamps == sorted(timestamps)
        assert timestamps[0] == pytest.approx(0.0, abs=0.05)
        assert timestamps[1] == pytest.approx(0.1, abs=0.05)
        assert timestamps[2] == pytest.approx(0.2, abs=0.05)

    @pytest.mark.anyio
    async def test_start_time_skips_initial_frames(self, sample_video):
        """start_time=1s skips first 10 frames at fps=10."""
        config = make_config(sample_video, start_time="1s")
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        # Total 30 frames, start at frame 10 → 20 remaining (allow ±1 for seek drift).
        assert 19 <= len(result) <= 21
        assert result[0]["timestamp"] >= 0.9

    @pytest.mark.anyio
    async def test_end_time_truncates_output(self, sample_video):
        """end_time=1s extracts roughly the first second (~10 frames at fps=10)."""
        config = make_config(sample_video, end_time="1s")
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert 9 <= len(result) <= 11

    @pytest.mark.anyio
    async def test_invalid_frame_interval_raises(self, sample_video):
        config = make_config(sample_video, frame_interval=0)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        with pytest.raises(ValueError, match="frame_interval"):
            await action.run(ctx, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_invalid_max_frame_count_raises(self, sample_video):
        config = make_config(sample_video, max_frame_count=0)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        with pytest.raises(ValueError, match="max_frame_count"):
            await action.run(ctx, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_registers_result_source(self, sample_video):
        config = make_config(sample_video, max_frame_count=2)
        action = OpenCVVideoFrameExtractorAction(config)
        ctx = make_context()

        await action.run(ctx, asyncio.get_running_loop())

        result_calls = [c for c in ctx.register_source.call_args_list if c.args[0] == "result"]
        assert len(result_calls) == 1


# -----------------------------------------------------------------------------
# Single B + streaming=true
# -----------------------------------------------------------------------------

class TestOpenCVSingleVideoStream:
    @pytest.mark.anyio
    async def test_returns_async_iterator_of_frames(self, sample_video):
        action = OpenCVVideoFrameExtractorAction(make_config(sample_video, streaming=True))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert isinstance(result, StreamChunkIterator)

        frames = await _collect_async(result)
        assert len(frames) == 30
        for frame in frames:
            _assert_frame(frame)


# -----------------------------------------------------------------------------
# List[B]
# -----------------------------------------------------------------------------

class TestOpenCVListInputCollect:
    @pytest.mark.anyio
    async def test_returns_list_of_frame_lists(self, sample_videos):
        action = OpenCVVideoFrameExtractorAction(make_config(sample_videos))
        ctx = make_context(resolved_video=[_media_source(p) for p in sample_videos])
        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == len(sample_videos)
        for per_video in result:
            assert isinstance(per_video, list)
            assert len(per_video) > 0
            for frame in per_video:
                _assert_frame(frame)


class TestOpenCVListInputStream:
    @pytest.mark.anyio
    async def test_returns_list_of_stream_iterators(self, sample_videos):
        action = OpenCVVideoFrameExtractorAction(make_config(sample_videos, streaming=True))
        ctx = make_context(resolved_video=[_media_source(p) for p in sample_videos])
        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == len(sample_videos)
        for per_video in result:
            assert isinstance(per_video, StreamChunkIterator)

        for per_video in result:
            frames = await _collect_async(per_video)
            assert len(frames) > 0
            for frame in frames:
                _assert_frame(frame)


# -----------------------------------------------------------------------------
# AsyncIterator[B]
# -----------------------------------------------------------------------------

class TestOpenCVAsyncInputCollect:
    @pytest.mark.anyio
    async def test_yields_per_video_frame_lists(self, sample_videos):
        action = OpenCVVideoFrameExtractorAction(make_config(sample_videos[0]))
        ctx = make_context(resolved_video=_async_media_iter(sample_videos))
        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        assert not isinstance(result, StreamChunkIterator)

        per_video_results = await _collect_async(result)
        assert len(per_video_results) == len(sample_videos)
        for per_video in per_video_results:
            assert isinstance(per_video, list)
            assert len(per_video) > 0
            for frame in per_video:
                _assert_frame(frame)


class TestOpenCVAsyncInputStream:
    @pytest.mark.anyio
    async def test_yields_per_video_stream_iterators(self, sample_videos):
        action = OpenCVVideoFrameExtractorAction(make_config(sample_videos[0], streaming=True))
        ctx = make_context(resolved_video=_async_media_iter(sample_videos))
        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        assert not isinstance(result, StreamChunkIterator)

        inner_frame_counts = []
        async for per_video in result:
            assert isinstance(per_video, StreamChunkIterator)
            frames = await _collect_async(per_video)
            inner_frame_counts.append(len(frames))
            for frame in frames:
                _assert_frame(frame)

        assert len(inner_frame_counts) == len(sample_videos)
        assert all(c > 0 for c in inner_frame_counts)
