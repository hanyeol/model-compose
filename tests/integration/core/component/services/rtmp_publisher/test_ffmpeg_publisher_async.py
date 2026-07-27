"""Async / non-blocking tests for the FFmpeg RTMP publisher driver.

No real RTMP server is spun up — the driver simply passes `self.url` to
`ffmpeg -f <format> <url>`, so a local file path acts as a fine "endpoint"
for these tests.

Verifies:
  - `FFmpegRtmpPublisher.publish(...)` yields the event loop while ffmpeg runs
    (ffmpeg is a native asyncio subprocess — the loop must stay responsive).
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
"""

from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.rtmp_publisher.base import RtmpPublisherService
from mindor.core.component.services.rtmp_publisher.drivers.ffmpeg import (
    FFmpegRtmpPublisher,
    FFmpegRtmpPublisherAction,
    FFmpegRtmpPublisherService,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.dsl.schema.action import RtmpPublisherActionConfig

from tests.async_helpers import assert_does_not_block


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _default_encoding():
    from mindor.core.foundation.media.encoding import (
        VideoAudioEncodingParams, VideoEncoderParams, AudioEncoderParams,
    )
    return VideoAudioEncodingParams(
        format="flv",
        video=VideoEncoderParams(codec="libx264"),
        audio=AudioEncoderParams(codec="aac"),
    )


@pytest.fixture(scope="module")
def sample_mp4_path():
    """~1s h264+aac mp4 for file-input publish."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=12",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def slow_publish_mp4_path():
    """Slightly longer mp4 — ~1.5s — so ffmpeg's wall time dominates the
    ticker interval and the non-blocking assertion is meaningful.
    """
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1.5:size=320x240:rate=24",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _make_context() -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    ctx.register_source = MagicMock()

    async def render_variable(value, **kwargs):
        return value

    async def render_video(value):
        # For the Action-level tests we render a MediaSource from a file path.
        from mindor.core.foundation.streaming.file import FileStreamResource
        return MediaSource(stream=FileStreamResource(value), format="mp4")

    async def render_audio(value):
        return None

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


@ffmpeg_required
class TestFFmpegRtmpPublisherAsync:

    @pytest.mark.anyio
    async def test_publish_does_not_block_event_loop(self, slow_publish_mp4_path, tmp_path):
        """ffmpeg is a native asyncio subprocess — the loop must remain responsive."""
        out = tmp_path / "out.flv"
        publisher = FFmpegRtmpPublisher(url=str(out), encoding=_default_encoding())

        await assert_does_not_block(
            publisher.publish(
                video=slow_publish_mp4_path,
                video_attrs=None,
                audio=None,
                audio_attrs=None,
            ),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert out.exists() and out.stat().st_size > 0

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_mp4_path, tmp_path):
        """After the refactor, `Service._run` takes (action, context) only — no `loop`."""
        sig = inspect.signature(FFmpegRtmpPublisherService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        # Positive-run: dispatch through the service with a file-URL target.
        service = FFmpegRtmpPublisherService.__new__(FFmpegRtmpPublisherService)
        RtmpPublisherService.__init__(service, "rtmp", MagicMock(), False)

        out = tmp_path / "out.flv"
        config = RtmpPublisherActionConfig(
            url=str(out),
            video="<placeholder>",
        )
        ctx = _make_context()

        # Route render_video through the fixture path.
        async def _render_video_local(value):
            from mindor.core.foundation.streaming.file import FileStreamResource
            return MediaSource(stream=FileStreamResource(sample_mp4_path), format="mp4")

        ctx.render_video = AsyncMock(side_effect=_render_video_local)

        result = await service._run(config, ctx)
        assert result is None
        assert out.exists() and out.stat().st_size > 0

    @pytest.mark.anyio
    async def test_action_publish_file_writes_output(self, sample_mp4_path, tmp_path):
        """Drive the Action end-to-end with a file source and file URL target."""
        out = tmp_path / "action-out.flv"
        config = RtmpPublisherActionConfig(
            url=str(out),
            video="<placeholder>",
        )
        ctx = _make_context()

        async def _render_video_local(value):
            from mindor.core.foundation.streaming.file import FileStreamResource
            return MediaSource(stream=FileStreamResource(sample_mp4_path), format="mp4")

        ctx.render_video = AsyncMock(side_effect=_render_video_local)

        result = await FFmpegRtmpPublisherAction(config).run(ctx)
        assert result is None
        assert out.exists() and out.stat().st_size > 0
