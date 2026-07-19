"""Tests for the FFmpeg video-frame-extractor driver.

Verifies the identity-preserving output container rules across the input × streaming matrix:

    | input \\ streaming  | false              | true                          |
    |---------------------|--------------------|-------------------------------|
    | B                   | List[F]            | AsyncIterator[F]              |
    | List[B]             | List[List[F]]      | List[AsyncIterator[F]]        |
    | AsyncIterator[B]    | AsyncIter[List[F]] | AsyncIter[AsyncIterator[F]]   |
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
from mindor.core.component.services.video_frame_extractor.drivers.ffmpeg import FFmpegVideoFrameExtractorAction
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"),
    reason="ffmpeg not installed",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_context(resolved_video: Any = None):
    """Mock context.

    `resolved_video` controls what `render_video` returns regardless of the configured
    `video` field — used for List[B] and AsyncIterator[B] cases where Pydantic would
    otherwise reject non-string inputs at config-construction time.
    """
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
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


@pytest.fixture(scope="module")
def sample_video():
    """Generate a small deterministic test video with ffmpeg's `testsrc`."""
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
    """Two deterministic test videos. Both are produced separately so we can
    independently assert per-video frame counts in batch / streaming inputs."""
    paths: List[str] = []

    for duration_s, rate in [(1, 10), (2, 5)]:  # → 10 frames, 10 frames
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
            pytest.skip(f"ffmpeg failed to generate test video: {e.stderr.decode('utf-8', errors='replace')}")
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


async def _collect_async(iterable: AsyncIterator[Any]) -> list:
    out = []
    async for item in iterable:
        out.append(item)
    return out


# -----------------------------------------------------------------------------
# Single B
# -----------------------------------------------------------------------------

class TestSingleVideoCollect:
    """B + streaming=false → List[F]"""

    @pytest.mark.anyio
    async def test_returns_list_of_frames(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 30
        for frame in result:
            _assert_frame(frame)


class TestSingleVideoStream:
    """B + streaming=true → AsyncIterator[F] (wrapped in StreamChunkIterator)"""

    @pytest.mark.anyio
    async def test_returns_async_iterator_of_frames(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, streaming=True))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert isinstance(result, StreamChunkIterator)

        frames = await _collect_async(result)
        assert len(frames) == 30
        for frame in frames:
            _assert_frame(frame)


# -----------------------------------------------------------------------------
# List[B]
# -----------------------------------------------------------------------------

class TestListInputCollect:
    """List[B] + streaming=false → List[List[F]]"""

    @pytest.mark.anyio
    async def test_returns_list_of_frame_lists(self, sample_videos):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_videos))
        ctx = make_context(resolved_video=[_media_source(p) for p in sample_videos])
        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == len(sample_videos)
        for per_video in result:
            assert isinstance(per_video, list)
            assert len(per_video) > 0
            for frame in per_video:
                _assert_frame(frame)


class TestListInputStream:
    """List[B] + streaming=true → List[AsyncIterator[F]]"""

    @pytest.mark.anyio
    async def test_returns_list_of_stream_iterators(self, sample_videos):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_videos, streaming=True))
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

async def _async_media_iter(paths: List[str]) -> AsyncIterator[MediaSource]:
    for path in paths:
        yield _media_source(path)


class TestAsyncInputCollect:
    """AsyncIterator[B] + streaming=false → AsyncIterator[List[F]]"""

    @pytest.mark.anyio
    async def test_yields_per_video_frame_lists(self, sample_videos):
        # config.video is a dummy string; ctx.render_video returns the async iterator.
        action = FFmpegVideoFrameExtractorAction(make_config(sample_videos[0]))
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


class TestAsyncInputStream:
    """AsyncIterator[B] + streaming=true → AsyncIterator[AsyncIterator[F]]"""

    @pytest.mark.anyio
    async def test_yields_per_video_stream_iterators(self, sample_videos):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_videos[0], streaming=True))
        ctx = make_context(resolved_video=_async_media_iter(sample_videos))
        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        assert not isinstance(result, StreamChunkIterator)

        # Verify both the outer container shape and that each inner item is consumable.
        inner_frame_counts = []
        async for per_video in result:
            assert isinstance(per_video, StreamChunkIterator)
            frames = await _collect_async(per_video)
            inner_frame_counts.append(len(frames))
            for frame in frames:
                _assert_frame(frame)

        assert len(inner_frame_counts) == len(sample_videos)
        assert all(c > 0 for c in inner_frame_counts)


# -----------------------------------------------------------------------------
# Misc — preserved from previous tests where still meaningful
# -----------------------------------------------------------------------------

class TestExtractionOptions:
    @pytest.mark.anyio
    async def test_frame_interval_skips_frames(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, frame_interval=2))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert len(result) == 15

    @pytest.mark.anyio
    async def test_max_frame_count_limits_output(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, max_frame_count=5))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert len(result) == 5

    @pytest.mark.anyio
    async def test_start_time_skips_initial_frames(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, start_time="1s"))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert 19 <= len(result) <= 21

    @pytest.mark.anyio
    async def test_end_time_truncates_output(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, end_time="1s"))
        result = await action.run(make_context(), asyncio.get_running_loop())

        assert 9 <= len(result) <= 11

    @pytest.mark.anyio
    async def test_timestamps_respect_interval(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, frame_interval=3, max_frame_count=5))
        result = await action.run(make_context(), asyncio.get_running_loop())

        timestamps = [chunk["timestamp"] for chunk in result]
        assert timestamps == [pytest.approx(t, abs=0.05) for t in [0.0, 0.3, 0.6, 0.9, 1.2]]

    @pytest.mark.anyio
    async def test_invalid_frame_interval_raises(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, frame_interval=0))
        with pytest.raises(ValueError, match="frame_interval"):
            await action.run(make_context(), asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_invalid_max_frame_count_raises(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(make_config(sample_video, max_frame_count=0))
        with pytest.raises(ValueError, match="max_frame_count"):
            await action.run(make_context(), asyncio.get_running_loop())


class TestOutputExpressionRendering:
    """${result[]} should be evaluated per chunk when the unit result is streaming."""

    @pytest.mark.anyio
    async def test_streaming_registers_result_brackets_per_chunk(self, sample_video):
        # Direct output (${result}) keeps the chunk yielded as-is so we can count chunks
        # without depending on render_variable's behavior.
        action = FFmpegVideoFrameExtractorAction(
            make_config(sample_video, streaming=True, output="${result}")
        )
        ctx = make_context()
        result = await action.run(ctx, asyncio.get_running_loop())

        # Consume the stream — each iteration corresponds to one chunk passing through
        # the streaming generator (which registers `result[]`).
        consumed = 0
        async for _ in result:
            consumed += 1

        assert consumed == 30
        bracket_calls = [c for c in ctx.register_source.call_args_list if c.args[0] == "result[]"]
        assert len(bracket_calls) == 30

    @pytest.mark.anyio
    async def test_non_streaming_registers_result(self, sample_video):
        action = FFmpegVideoFrameExtractorAction(
            make_config(sample_video, output="${result}")
        )
        ctx = make_context()
        await action.run(ctx, asyncio.get_running_loop())

        result_calls = [c for c in ctx.register_source.call_args_list if c.args[0] == "result"]
        assert len(result_calls) >= 1
