"""Async / non-blocking tests for the TransNetV2 video-scene-detector driver.

TransNetV2 wraps a TensorFlow model, so its real `_predict` is patched out
in these tests. The stand-in blocks the calling thread for ~200ms, which is
enough for the ticker to prove `_predict` is being run via
`_run_in_executor` (not on the loop).

Verifies:
  - `Action.run(context)` yields the event loop while the sync predictor runs.
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
  - Batch (list) input returns list-of-lists.
"""

from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_scene_detector.base import (
    VideoSceneDetectorService,
)
from mindor.core.component.services.video_scene_detector.drivers.transnetv2 import (
    TransNetV2VideoSceneDetectorAction,
    TransNetV2VideoSceneDetectorService,
)
from mindor.core.foundation.streaming.media import MediaSource, create_media_source
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig

from tests.async_helpers import assert_does_not_block


ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not available on PATH",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """Tiny mp4 — ffprobe reads frame_rate from it during detection."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _make_context(video_value: Any) -> ComponentActionContext:
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

    async def render_scalar(value, cast, default=None):
        if value is None:
            return default
        return cast(value)

    async def render_time(value, default=None):
        if value is None:
            return default
        from mindor.core.foundation.variable.time import parse_time
        return parse_time(value)

    async def render_string(value, default=None):
        if value is None or value == "":
            return default
        return value

    ctx.render_scalar = AsyncMock(side_effect=render_scalar)
    ctx.render_time = AsyncMock(side_effect=render_time)
    ctx.render_string = AsyncMock(side_effect=render_string)
    return ctx


def _make_config(**kwargs) -> VideoSceneDetectorActionConfig:
    payload = {"video": "<placeholder>", **kwargs}
    return VideoSceneDetectorActionConfig(**payload)


def _slow_predict_factory(sleep_s: float = 0.2):
    """Return a `_predict` stand-in that mimics a CPU-bound sync call.

    Blocks for `sleep_s` seconds on the calling thread — if the driver is
    correctly using `_run_in_executor`, the event loop stays responsive.
    """
    import numpy as np

    def _predict(video: str):
        time.sleep(sleep_s)
        return np.array([0.1] * 20, dtype=np.float32)

    return _predict


@ffmpeg_required
class TestTransNetV2VideoSceneDetectorAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self, sample_video):
        """`_predict` is sync CPU-bound and MUST be offloaded via `_run_in_executor`."""
        fake_predict = _slow_predict_factory(sleep_s=0.3)

        action = TransNetV2VideoSceneDetectorAction(_make_config())
        ctx = _make_context(sample_video)

        with patch.object(
            TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)
        ):
            result = await assert_does_not_block(
                action.run(ctx),
                tick_interval_s=0.01,
                min_ticks=5,
            )

        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_video):
        sig = inspect.signature(TransNetV2VideoSceneDetectorService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        service = TransNetV2VideoSceneDetectorService.__new__(TransNetV2VideoSceneDetectorService)
        VideoSceneDetectorService.__init__(service, "vsd", MagicMock(), False)

        ctx = _make_context(sample_video)
        fake_predict = _slow_predict_factory(sleep_s=0.05)
        with patch.object(
            TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)
        ):
            result = await service._run(_make_config(), ctx)
        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_batch_input_processes_each(self, sample_video):
        """List input returns List[List[Scene]]. Each item independently runs _predict."""
        fake_predict = _slow_predict_factory(sleep_s=0.15)

        action = TransNetV2VideoSceneDetectorAction(_make_config())
        ctx = _make_context([sample_video, sample_video])

        with patch.object(
            TransNetV2VideoSceneDetectorAction, "_predict", staticmethod(fake_predict)
        ):
            result = await assert_does_not_block(
                action.run(ctx),
                tick_interval_s=0.01,
                min_ticks=5,
            )

        assert isinstance(result, list)
        assert len(result) == 2
        for per_video in result:
            assert isinstance(per_video, list)
