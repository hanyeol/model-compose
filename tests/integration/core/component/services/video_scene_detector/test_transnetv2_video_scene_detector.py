"""Tests for the TransNetV2 video-scene-detector driver.

TransNetV2 pulls in a heavy TensorFlow model, so the full e2e path is skipped when the package is
unavailable. We still verify input path resolution by mocking out the model invocation.
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.utils.streaming.media import MediaSource, create_media_source
from mindor.core.utils.streaming.file import FileStreamResource
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.component.services.video_scene_detector.drivers.transnetv2 import (
    TransNetV2VideoSceneDetectorAction,
)

# We never import the real transnetv2 package — _predict is always patched in these tests.


ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """Tiny mp4 — large enough for ffprobe to read frame_rate."""
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
class TestInputPathResolution:
    """Verify input strategies without loading the actual TransNetV2 model."""

    @pytest.mark.anyio
    async def test_file_stream_resource_uses_path_directly(self, sample_video):
        """A MediaSource backed by FileStreamResource should be fed straight to the predictor."""
        import numpy as np

        observed_paths: list[str] = []

        def fake_predict(video):
            observed_paths.append(video)
            # Single-scene prediction (all below threshold).
            return np.array([0.1] * 10, dtype=np.float32)

        source = MediaSource(FileStreamResource(sample_video))
        config = _make_config()
        ctx = _make_context(source)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert observed_paths == [sample_video], "FileStreamResource path should pass through unchanged"
        assert isinstance(result, dict)
        assert "scenes" in result

    @pytest.mark.anyio
    async def test_bytes_input_is_spooled(self, sample_video):
        """In-memory bytes should be spooled to a path before the predictor runs."""
        import numpy as np

        observed_paths: list[str] = []

        def fake_predict(video):
            observed_paths.append(video)
            return np.array([0.1] * 10, dtype=np.float32)

        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format="mp4")
        config = _make_config()
        ctx = _make_context(source)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert len(observed_paths) == 1
        # Spooled path must differ from the original input fixture.
        assert observed_paths[0] != sample_video
        assert isinstance(result, dict)

    @pytest.mark.anyio
    async def test_spooled_temp_file_is_cleaned_up(self, sample_video, monkeypatch):
        """After detection, the spooled temp file must be removed."""
        import numpy as np

        def fake_predict(video):
            return np.array([0.1] * 10, dtype=np.float32)

        with open(sample_video, "rb") as f:
            data = f.read()
        source = MediaSource(BytesStreamResource(data), format="mp4")
        config = _make_config()
        ctx = _make_context(source)

        spooled_paths: list[str] = []
        from mindor.core.component.services.video_scene_detector.drivers import transnetv2 as tn_mod
        original_save = tn_mod.save_stream_to_temporary_file

        async def tracking_save(stream, ext):
            path = await original_save(stream, ext)
            spooled_paths.append(path)
            return path

        monkeypatch.setattr(tn_mod, "save_stream_to_temporary_file", tracking_save)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert spooled_paths, "expected at least one spooled temp file"
        for path in spooled_paths:
            assert not os.path.exists(path), f"spooled file leaked: {path}"


@ffmpeg_required
class TestResultBuilding:
    """Verify result construction from mocked predictions."""

    @pytest.mark.anyio
    async def test_no_boundaries_yields_single_scene(self, sample_video):
        """All predictions below threshold → one wrapping scene only."""
        import numpy as np

        def fake_predict(video):
            return np.array([0.1] * 20, dtype=np.float32)

        config = _make_config()
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["total_scenes"] == 1

    @pytest.mark.anyio
    async def test_boundary_above_threshold_yields_two_scenes(self, sample_video):
        """One frame above threshold → boundary splits into multiple scenes."""
        import numpy as np

        predictions = np.array([0.1] * 20, dtype=np.float32)
        predictions[10] = 0.9
        def fake_predict(video):
            return predictions

        config = _make_config()
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["total_scenes"] >= 2

    @pytest.mark.anyio
    async def test_scene_entry_schema(self, sample_video):
        """Each scene dict carries the expected fields/types."""
        import numpy as np

        def fake_predict(video):
            return np.array([0.1] * 10, dtype=np.float32)

        config = _make_config()
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        scene = result["scenes"][0]
        for key in ("index", "start", "end", "start_frame", "end_frame", "duration"):
            assert key in scene, f"missing field: {key}"
        assert isinstance(scene["index"], int)
        assert isinstance(scene["start_frame"], int)
        assert isinstance(scene["end_frame"], int)


# Fixture video is 1 second @ 10 fps → frame_rate = 10.

@ffmpeg_required
class TestTimeFiltering:
    """Verify start_time / end_time slicing on the prediction array."""

    @pytest.mark.anyio
    async def test_start_time_skips_early_boundary(self, sample_video):
        """A boundary inside the skipped prefix should be discarded."""
        import numpy as np

        predictions = np.array([0.1] * 20, dtype=np.float32)
        predictions[2] = 0.9  # boundary at frame 2 → 0.2s
        def fake_predict(video):
            return predictions

        # start_time=0.5s → skip first 5 frames → boundary at frame 2 is filtered out.
        config = _make_config(start_time="00:00:00.5")
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["total_scenes"] == 1

    @pytest.mark.anyio
    async def test_end_time_skips_late_boundary(self, sample_video):
        """A boundary past end_time should be discarded."""
        import numpy as np

        predictions = np.array([0.1] * 20, dtype=np.float32)
        predictions[15] = 0.9  # boundary at frame 15 → 1.5s
        def fake_predict(video):
            return predictions

        # end_time=1.0s → keep first 10 frames → boundary at frame 15 is sliced away.
        config = _make_config(end_time="00:00:01.0")
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["total_scenes"] == 1

    @pytest.mark.anyio
    async def test_time_window_keeps_inner_boundary(self, sample_video):
        """A boundary inside the [start_time, end_time] window survives."""
        import numpy as np

        predictions = np.array([0.1] * 20, dtype=np.float32)
        predictions[12] = 0.9  # boundary at frame 12 → 1.2s
        def fake_predict(video):
            return predictions

        # Window [1.0s, 1.5s] → frames 10..14 → boundary at frame 12 (relative 2) is kept.
        config = _make_config(start_time="00:00:01.0", end_time="00:00:01.5")
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["total_scenes"] >= 2

    @pytest.mark.anyio
    async def test_empty_window_yields_no_scenes(self, sample_video):
        """end_time < start_time slices the array to empty → no scenes at all."""
        import numpy as np

        def fake_predict(video):
            return np.array([0.1] * 20, dtype=np.float32)

        config = _make_config(start_time="00:00:01.5", end_time="00:00:00.5")
        ctx = _make_context(sample_video)

        with patch.object(TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)):
            result = await TransNetV2VideoSceneDetectorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["total_scenes"] == 0
