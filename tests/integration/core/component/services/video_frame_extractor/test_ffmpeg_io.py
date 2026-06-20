"""Tests for the VideoFrameExtractorAction I/O matrix.

Verifies the identity-preserving container rules across (input × streaming) and the
output-expression behavior on the unit result (${result} / ${result[]}):

    | input \\ streaming  | false              | true                              |
    |---------------------|--------------------|-----------------------------------|
    | B                   | List[F]            | StreamChunkIterator               |
    | List[B]             | List[List[F]]      | List[StreamChunkIterator]         |
    | AsyncIterator[B]    | AsyncIter[List[F]] | AsyncIter[StreamChunkIterator]    |

`${result[]}` is only meaningful when the unit result is an AsyncIterable (streaming=true);
it refers to a single chunk and is evaluated per chunk inside StreamChunkIterator.

Uses the FFmpeg driver as the concrete implementation; the I/O machinery is shared
across drivers via the common VideoFrameExtractorAction base.
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

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_frame_extractor.drivers.ffmpeg import FFmpegVideoFrameExtractorAction
from mindor.core.utils.iterators import StreamChunkIterator
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.utils.streaming.file import FileStreamResource
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"),
    reason="ffmpeg not installed",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"ffmpeg failed: {e.stderr.decode('utf-8', errors='replace')}")
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _make_media_source(path: str) -> MediaSource:
    return MediaSource(stream=FileStreamResource(path), format="mp4")


async def _make_async_iter(items: list):
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [item async for item in stream]


def _make_context(video_value: Any, output: Any = None) -> ComponentActionContext:
    """Build a mock context where render_video resolves inputs into MediaSource(s)."""
    ctx = MagicMock(spec=ComponentActionContext)

    # Track registered sources so render_variable can resolve `${result[]}` to the
    # last-registered element value.
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        if key == "result[]" and isinstance(value, str):
            return "${result[]" in value
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        return value
    ctx.render_variable = AsyncMock(side_effect=render_variable)

    # Resolve the configured video field into MediaSource(s) by structural inspection.
    async def render_video(_value):
        if callable(video_value) and not isinstance(video_value, str):
            source = video_value()
            assert isinstance(source, AsyncIterator)

            async def _map():
                async for path in source:
                    yield _make_media_source(path)
            return _map()
        if isinstance(video_value, list):
            return [_make_media_source(p) for p in video_value]
        if isinstance(video_value, AsyncIterator):
            async def _gen():
                async for path in video_value:
                    yield _make_media_source(path)
            return _gen()
        return _make_media_source(video_value)

    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


def _make_config(output: Any = None, **kwargs) -> VideoFrameExtractorActionConfig:
    payload = {"video": "<placeholder>", "max_frame_count": 3, **kwargs}
    if output is not None:
        payload["output"] = output
    return VideoFrameExtractorActionConfig(**payload)


class TestSingleVideoInput:
    @pytest.mark.anyio
    async def test_no_output_returns_list_of_frames(self, sample_video):
        config = _make_config()
        ctx = _make_context(sample_video)
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.anyio
    async def test_passthrough_output_returns_list_of_frames(self, sample_video):
        config = _make_config(output="${result}")
        ctx = _make_context(sample_video, output="${result}")
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.anyio
    async def test_stream_output_template_no_longer_triggers_stream_mode(self, sample_video):
        # ${result[]} no longer forces stream mode; without streaming=true, the unit
        # result is a List[F] and ${result[]} is meaningless (registers nothing useful).
        # The driver still returns the collected list — output template is rendered once
        # over the non-streaming unit result.
        config = _make_config(output="${result[]}")
        ctx = _make_context(sample_video, output="${result[]}")
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)


class TestListVideoInput:
    @pytest.mark.anyio
    async def test_list_no_output_returns_list_of_frame_lists(self, sample_video):
        config = _make_config()
        ctx = _make_context([sample_video, sample_video])
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(r) == 3 for r in result)

    @pytest.mark.anyio
    async def test_list_stream_output_template_no_longer_triggers_stream_mode(self, sample_video):
        # Same as the single-input case: ${result[]} alone doesn't activate streaming.
        # The output expression is still evaluated once at the end; since result[] is
        # only meaningful for streaming unit results, the rendered value is None here.
        config = _make_config(output="${result[]}")
        ctx = _make_context([sample_video, sample_video], output="${result[]}")
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)


class TestStreamingOption:
    @pytest.mark.anyio
    async def test_streaming_true_returns_stream_chunk_iterator(self, sample_video):
        # B + streaming=true → AsyncIterator[F] wrapped in StreamChunkIterator.
        config = _make_config(streaming=True)
        ctx = _make_context(sample_video)
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, StreamChunkIterator)
        frames = await _collect(result)
        assert len(frames) == 3

    @pytest.mark.anyio
    async def test_streaming_true_with_list_returns_list_of_streams(self, sample_video):
        # List[B] + streaming=true → List[StreamChunkIterator] (one stream per video).
        config = _make_config(streaming=True)
        ctx = _make_context([sample_video, sample_video])
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for per_video in result:
            assert isinstance(per_video, StreamChunkIterator)

        for per_video in result:
            frames = await _collect(per_video)
            assert len(frames) == 3


class TestStreamInput:
    """AsyncIterator[B] input preserves the outer container shape (stream-in → stream-out).

    Per the new model, the inner shape is decided by `streaming`:
      - streaming=false → AsyncIterator[List[F]]
      - streaming=true  → AsyncIterator[StreamChunkIterator]
    """

    @pytest.mark.anyio
    async def test_stream_input_collect_yields_per_video_lists(self, sample_video):
        def _make_iter():
            async def _gen():
                yield sample_video
                yield sample_video
            return _gen()

        config = _make_config()
        ctx = _make_context(_make_iter)
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 2
        assert all(isinstance(per_video, list) and len(per_video) == 3 for per_video in items)

    @pytest.mark.anyio
    async def test_stream_input_streaming_yields_per_video_streams(self, sample_video):
        def _make_iter():
            async def _gen():
                yield sample_video
                yield sample_video
                yield sample_video
            return _gen()

        config = _make_config(streaming=True)
        ctx = _make_context(_make_iter)
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)

        per_video_frame_counts = []
        async for per_video in result:
            assert isinstance(per_video, StreamChunkIterator)
            frames = await _collect(per_video)
            per_video_frame_counts.append(len(frames))

        assert per_video_frame_counts == [3, 3, 3]


class TestBatchSize:
    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 4])
    async def test_list_input_various_batch_sizes(self, sample_video, batch_size: int):
        config = _make_config(batch_size=batch_size)
        videos = [sample_video] * 3
        ctx = _make_context(videos)
        result = await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(r) == 3 for r in result)


class TestErrors:
    @pytest.mark.anyio
    async def test_invalid_frame_interval(self, sample_video):
        config = _make_config(frame_interval=0)
        ctx = _make_context(sample_video)
        with pytest.raises(ValueError, match="frame_interval"):
            await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_invalid_max_frame_count(self, sample_video):
        config = _make_config(max_frame_count=0)
        ctx = _make_context(sample_video)
        with pytest.raises(ValueError, match="max_frame_count"):
            await FFmpegVideoFrameExtractorAction(config).run(ctx, asyncio.get_running_loop())
