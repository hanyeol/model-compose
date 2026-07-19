"""Tests for the FFmpeg video-scene-detector driver.

Covers three layers:
  - Scene detection behavior (threshold / time range / schema / errors)
  - Input path resolution (FileStreamResource path / spooled fallback)
  - I/O matrix (single / list input, ${result[]} stream output, batch_size)
"""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_scene_detector.drivers.ffmpeg import (
    FFmpegVideoSceneDetectorAction,
)
from mindor.core.foundation.streaming.media import MediaSource, create_media_source
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig


ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not available on PATH",
)

_TIMECODE_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d+$")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """Single-scene video (testsrc only, low scene-change activity)."""
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


@pytest.fixture(scope="module")
def multi_scene_video():
    """Two-segment video concatenated from solid color and a moving testsrc, guaranteeing a hard scene cut."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=red:size=64x48:duration=1:rate=10",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
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


def _make_context(video_value: Any) -> ComponentActionContext:
    """Build a mock context where render_video yields MediaSource(s).

    `video_value` can be:
      - str: treated as file path → FileStreamResource path
      - bytes: treated as in-memory data → BytesStreamResource
      - MediaSource: passed through as-is
      - list of any of the above: returned as list
    """
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        return value

    def resolve_one(value):
        if isinstance(value, MediaSource):
            return value
        return create_media_source(value)

    async def render_video(_value):
        if isinstance(video_value, list):
            return [resolve_one(v) for v in video_value]
        return resolve_one(video_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


def _make_config(output: Any = None, **kwargs) -> VideoSceneDetectorActionConfig:
    payload = {"video": "<placeholder>", **kwargs}
    if output is not None:
        payload["output"] = output
    return VideoSceneDetectorActionConfig(**payload)


@ffmpeg_required
class TestFFmpegVideoSceneDetector:
    """End-to-end scene detection behavior for a single input."""

    @pytest.mark.anyio
    async def test_result_schema(self, sample_video):
        config = _make_config()
        ctx = _make_context(sample_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_scene_entry_schema(self, sample_video):
        config = _make_config()
        ctx = _make_context(sample_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())
        scene = result[0]

        # Required fields.
        for key in ("index", "start", "end", "start_frame", "end_frame", "duration"):
            assert key in scene, f"missing field: {key}"

        # Types & formats.
        assert isinstance(scene["index"], int)
        assert isinstance(scene["start_frame"], int)
        assert isinstance(scene["end_frame"], int)
        assert _TIMECODE_PATTERN.match(scene["start"]), f"bad start: {scene['start']}"
        assert _TIMECODE_PATTERN.match(scene["end"]), f"bad end: {scene['end']}"
        assert _TIMECODE_PATTERN.match(scene["duration"]), f"bad duration: {scene['duration']}"

    @pytest.mark.anyio
    async def test_detects_multiple_scenes(self, multi_scene_video):
        # A solid-color → testsrc concat produces a hard scene cut; default threshold should pick it up.
        config = _make_config()
        ctx = _make_context(multi_scene_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert len(result) >= 2

    @pytest.mark.anyio
    async def test_high_threshold_reduces_scenes(self, multi_scene_video):
        # Threshold near 1.0 should suppress all detected boundaries.
        config = _make_config(threshold="0.99")
        ctx = _make_context(multi_scene_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        # Still one wrapping scene (boundaries=[0, duration]), but no internal cuts.
        assert len(result) == 1

    @pytest.mark.anyio
    async def test_start_time_option(self, multi_scene_video):
        # start_time after the cut → no internal boundary remains.
        config = _make_config(start_time="00:00:01.5")
        ctx = _make_context(multi_scene_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert len(result) == 1

    @pytest.mark.anyio
    async def test_end_time_option(self, multi_scene_video):
        # end_time before the cut → no internal boundary remains.
        config = _make_config(end_time="00:00:00.5")
        ctx = _make_context(multi_scene_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert len(result) == 1

    @pytest.mark.anyio
    async def test_invalid_input_raises_runtime_error(self, tmp_path):
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"not a video file at all" * 32)

        config = _make_config()
        ctx = _make_context(str(bogus))

        with pytest.raises(RuntimeError):
            await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_output_template_overrides_return_value(self, sample_video):
        config = _make_config(output="detected")
        ctx = _make_context(sample_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result == "detected"
        registered = dict(c.args for c in ctx.register_source.call_args_list)
        assert "result" in registered
        assert isinstance(registered["result"], list)


@ffmpeg_required
class TestInputPathResolution:
    """Verify input strategies: file path / spooled fallback."""

    @pytest.mark.anyio
    async def test_file_stream_resource_uses_path_directly(self, sample_video):
        """A MediaSource backed by FileStreamResource should be fed via -i <path>."""
        source = MediaSource(FileStreamResource(sample_video))
        config = _make_config()
        ctx = _make_context(source)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_bytes_input_is_spooled(self, sample_video):
        """In-memory video bytes should be spooled to a temp file before detection."""
        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format="mp4")
        config = _make_config()
        ctx = _make_context(source)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_unknown_format_is_spooled(self, sample_video):
        """Even when format is unknown, scene detection still falls back to spooling."""
        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format=None)
        config = _make_config()
        ctx = _make_context(source)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_string_path_is_treated_as_file(self, sample_video):
        """A plain string path should be normalized to a FileStreamResource-backed MediaSource."""
        config = _make_config()
        ctx = _make_context(sample_video)  # bare string

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_spooled_temp_file_is_cleaned_up(self, sample_video, monkeypatch):
        """After detection, the spooled temp file must be removed."""
        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format="mp4")
        config = _make_config()
        ctx = _make_context(source)

        spooled_paths: list[str] = []
        from mindor.core.component.services.video_scene_detector.drivers import ffmpeg as ffmpeg_mod
        original_save = ffmpeg_mod.save_stream_to_temporary_file

        async def tracking_save(stream, ext):
            path = await original_save(stream, ext)
            spooled_paths.append(path)
            return path

        monkeypatch.setattr(ffmpeg_mod, "save_stream_to_temporary_file", tracking_save)

        await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert spooled_paths, "expected at least one spooled temp file"
        for path in spooled_paths:
            assert not os.path.exists(path), f"spooled file leaked: {path}"


@ffmpeg_required
class TestSingleInput:
    """I/O matrix: single input with various output references."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_list(self, sample_video):
        config = _make_config()
        ctx = _make_context(sample_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_list(self, sample_video):
        config = _make_config(output="${result}")
        ctx = _make_context(sample_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)


@ffmpeg_required
class TestListInput:
    """I/O matrix: list input returns list of scene lists."""

    @pytest.mark.anyio
    async def test_list_returns_list_of_lists(self, sample_video):
        config = _make_config()
        ctx = _make_context([sample_video, sample_video])

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, list) for r in result)
        assert all(len(r) >= 1 for r in result)


@ffmpeg_required
class TestStreamOutput:
    """Under the new model `${result[]}` no longer forces stream mode; scene_detector's
    unit result is always a List (not AsyncIterable), so neither single nor list input
    produces an AsyncIterator output."""

    @pytest.mark.anyio
    async def test_stream_output_template_no_longer_triggers_stream_mode(self, sample_video):
        config = _make_config(output="${result[]}")
        ctx = _make_context(sample_video)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)

    @pytest.mark.anyio
    async def test_stream_output_template_with_list(self, sample_video):
        config = _make_config(output="${result[]}")
        ctx = _make_context([sample_video, sample_video])

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)


@ffmpeg_required
class TestBatchSize:
    """I/O matrix: batch_size affects internal chunking but not result shape."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 3])
    async def test_list_with_batch_size(self, sample_video, batch_size: int):
        config = _make_config(batch_size=batch_size)
        ctx = _make_context([sample_video] * 3)

        result = await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(r, list) for r in result)


@ffmpeg_required
class TestErrorPropagation:
    """I/O matrix: errors in list inputs propagate via asyncio.gather."""

    @pytest.mark.anyio
    async def test_invalid_input_in_list_raises(self, sample_video, tmp_path):
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"not a video file at all" * 32)

        config = _make_config()
        ctx = _make_context([sample_video, str(bogus)])

        with pytest.raises(RuntimeError):
            await FFmpegVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())
