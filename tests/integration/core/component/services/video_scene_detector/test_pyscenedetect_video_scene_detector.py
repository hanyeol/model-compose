"""Tests for the PySceneDetect video-scene-detector driver.

Covers:
  - Scene detection behavior (default detector, threshold, schema, errors)
  - Input path resolution (FileStreamResource path / spooled fallback)
  - I/O matrix (single / list input)
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.foundation.streaming.media import MediaSource, create_media_source
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig


scenedetect_available = pytest.importorskip("scenedetect", reason="scenedetect not installed")

from mindor.core.component.services.video_scene_detector.drivers.pyscenedetect import (
    PySceneVideoSceneDetectorAction,
)


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """Single-segment video."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=64x48:rate=10",
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
    """Three-segment video (red → green → testsrc) with hard cuts. PySceneDetect's content-based
    detector needs enough resolution and duration per segment to register a scene change."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=red:size=320x240:duration=1:rate=24",
        "-f", "lavfi", "-i", "color=c=green:size=320x240:duration=1:rate=24",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=24",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0",
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
    ctx = MagicMock(spec=ComponentActionContext)
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
class TestPySceneDetector:
    """End-to-end scene detection behavior."""

    @pytest.mark.anyio
    async def test_result_schema(self, sample_video):
        config = _make_config()
        ctx = _make_context(sample_video)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, dict)
        assert "scenes" in result
        assert "total_scenes" in result
        assert len(result["scenes"]) == result["total_scenes"]

    @pytest.mark.anyio
    async def test_scene_entry_schema(self, multi_scene_video):
        config = _make_config()
        ctx = _make_context(multi_scene_video)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        # Multi-scene fixture should yield at least one scene with all fields populated.
        assert result["total_scenes"] >= 1
        scene = result["scenes"][0]
        for key in ("index", "start", "end", "start_frame", "end_frame", "duration"):
            assert key in scene, f"missing field: {key}"
        assert isinstance(scene["index"], int)
        assert isinstance(scene["start_frame"], int)
        assert isinstance(scene["end_frame"], int)

    @pytest.mark.anyio
    async def test_detects_multiple_scenes(self, multi_scene_video):
        config = _make_config()
        ctx = _make_context(multi_scene_video)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        # Hard cut between solid color and testsrc.
        assert result["total_scenes"] >= 2

    @pytest.mark.anyio
    async def test_content_detector(self, multi_scene_video):
        config = _make_config(detector="content")
        ctx = _make_context(multi_scene_video)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, dict)
        assert result["total_scenes"] >= 1


@ffmpeg_required
class TestInputPathResolution:
    """Verify input strategies: file path / spooled fallback."""

    @pytest.mark.anyio
    async def test_file_stream_resource_uses_path_directly(self, sample_video):
        source = MediaSource(FileStreamResource(sample_video))
        config = _make_config()
        ctx = _make_context(source)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, dict)

    @pytest.mark.anyio
    async def test_bytes_input_is_spooled(self, sample_video):
        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format="mp4")
        config = _make_config()
        ctx = _make_context(source)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, dict)

    @pytest.mark.anyio
    async def test_spooled_temp_file_is_cleaned_up(self, sample_video, monkeypatch):
        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format="mp4")
        config = _make_config()
        ctx = _make_context(source)

        spooled_paths: list[str] = []
        from mindor.core.component.services.video_scene_detector.drivers import pyscenedetect as ps_mod
        original_save = ps_mod.save_stream_to_temporary_file

        async def tracking_save(stream, ext):
            path = await original_save(stream, ext)
            spooled_paths.append(path)
            return path

        monkeypatch.setattr(ps_mod, "save_stream_to_temporary_file", tracking_save)

        await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert spooled_paths, "expected at least one spooled temp file"
        for path in spooled_paths:
            assert not os.path.exists(path), f"spooled file leaked: {path}"


@ffmpeg_required
class TestSingleInput:
    """I/O matrix: single input."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_dict(self, sample_video):
        config = _make_config()
        ctx = _make_context(sample_video)

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, dict)
        assert "scenes" in result and "total_scenes" in result


@ffmpeg_required
class TestListInput:
    """I/O matrix: list input."""

    @pytest.mark.anyio
    async def test_list_returns_list_of_dicts(self, sample_video):
        config = _make_config()
        ctx = _make_context([sample_video, sample_video])

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, dict) for r in result)


@ffmpeg_required
class TestStreamOutput:
    """Under the new model `${result[]}` no longer forces stream mode; scene_detector's
    unit result is always a Dict (not AsyncIterable), so AsyncIterator output never appears."""

    @pytest.mark.anyio
    async def test_stream_output_template_no_longer_triggers_stream_mode(self, sample_video):
        config = _make_config(output="${result[]}")
        ctx = _make_context([sample_video, sample_video])

        result = await PySceneVideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)
