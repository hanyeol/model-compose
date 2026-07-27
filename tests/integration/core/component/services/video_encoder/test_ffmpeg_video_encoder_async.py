"""Async / non-blocking tests for the FFmpeg video-encoder driver.

Verifies:
  - `Action.run(context)` yields the event loop while ffmpeg encodes frames.
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
  - Batch input (multiple frame sequences) is processed end-to-end.
  - A CancellationToken mid-run terminates ffmpeg promptly.
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
from typing import Any, Callable, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_encoder.base import VideoEncoderService
from mindor.core.component.services.video_encoder.drivers.ffmpeg import (
    FFmpegVideoEncoderAction,
    FFmpegVideoEncoderService,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.dsl.schema.action.impl.media import (
    AudioEncoderConfig,
    VideoAudioEncodingConfig,
    VideoEncoderConfig,
)

from tests.async_helpers import assert_does_not_block


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_frames(count: int = 60, size=(320, 240)) -> List[PILImage.Image]:
    """Solid-color RGB frames — enough to guarantee ffmpeg wall time > tick interval."""
    return [PILImage.new("RGB", size, (30 + (i * 3) % 220, 60, 120)) for i in range(count)]


@pytest.fixture(scope="module")
def sample_mp4_path():
    """Small ~2s mp4 with h264+aac."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _make_context(
    frames_value: Any = None,
    video_value: Any = None,
    *,
    cancellation_token=None,
) -> ComponentActionContext:
    from mindor.core.foundation.streaming.video import create_video_source

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = cancellation_token
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result}":
                return sources.get("result")
        return value

    def _resolve_video(v):
        if isinstance(v, str):
            with open(v, "rb") as f:
                v = f.read()
        return create_video_source(v)

    async def render_image_array(value):
        target = frames_value if frames_value is not None else value
        if callable(target) and not isinstance(target, (list, str)):
            src = target()
            assert isinstance(src, AsyncIterator)

            async def _map():
                async for chunk in src:
                    yield ImageArrayValue(list(chunk))
            return _map()
        return [ImageArrayValue(list(inner)) for inner in target]

    async def render_video(value):
        target = video_value if video_value is not None else value
        if callable(target) and not isinstance(target, str):
            src = target()
            assert isinstance(src, AsyncIterator)

            async def _map():
                async for item in src:
                    yield _resolve_video(item)
            return _map()
        if isinstance(target, list):
            return [_resolve_video(v) for v in target]
        return _resolve_video(target)

    async def render_audio(value):
        return None  # unused in these tests

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_image_array = AsyncMock(side_effect=render_image_array)
    ctx.render_video = AsyncMock(side_effect=render_video)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


def _make_config(**kwargs) -> VideoEncoderActionConfig:
    return VideoEncoderActionConfig(**kwargs)


@ffmpeg_required
class TestFFmpegVideoEncoderAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self):
        """Encoding a batch of frames must let the event loop tick."""
        frames = _make_frames(count=60)  # 60 frames × x264 encode → hundreds of ms
        config = _make_config(frames="${frames}", frame_rate=24)
        ctx = _make_context(frames_value=[frames])

        result = await assert_does_not_block(
            FFmpegVideoEncoderAction(config).run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], VideoStreamResource)
        await result[0].close()

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self):
        """After the refactor, `Service._run` takes (action, context) only — no `loop`."""
        sig = inspect.signature(FFmpegVideoEncoderService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        service = FFmpegVideoEncoderService.__new__(FFmpegVideoEncoderService)
        VideoEncoderService.__init__(service, "ve", MagicMock(), False)

        frames = _make_frames(count=24)
        config = _make_config(frames="${frames}", frame_rate=12)
        ctx = _make_context(frames_value=[frames])

        result = await service._run(config, ctx)
        assert isinstance(result, list)
        for item in result:
            await item.close()

    @pytest.mark.anyio
    async def test_batch_frame_sequences(self):
        """Encoding two frame sequences returns two video resources."""
        seq_a = _make_frames(count=24)
        seq_b = _make_frames(count=24)
        config = _make_config(frames="${frames}", frame_rate=12)
        ctx = _make_context(frames_value=[seq_a, seq_b])

        result = await assert_does_not_block(
            FFmpegVideoEncoderAction(config).run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, VideoStreamResource)
            await item.close()

    @pytest.mark.anyio
    async def test_video_passthrough_does_not_block(self, sample_mp4_path):
        """Existing-video encode path also uses ffmpeg subprocess — non-blocking."""
        config = _make_config(video="${video}")
        ctx = _make_context(video_value=sample_mp4_path)

        result = await assert_does_not_block(
            FFmpegVideoEncoderAction(config).run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, VideoStreamResource)
        await result.close()

    @pytest.mark.anyio
    async def test_cancellation_token_stops_encoding_promptly(self, tmp_path):
        """Firing the cancellation token mid-encode must abort ffmpeg well before EOF."""
        long_source = str(tmp_path / "long.mp4")
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-y",
                "-f", "lavfi", "-i", "testsrc=duration=10:size=640x480:rate=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                long_source,
            ],
            check=True, capture_output=True,
        )

        token = CancellationToken()
        ctx = _make_context(video_value=long_source, cancellation_token=token)
        config = _make_config(video="${video}")

        async def _cancel_soon():
            await asyncio.sleep(0.2)
            token.cancel(reason="test")

        canceller = asyncio.create_task(_cancel_soon())
        started = time.monotonic()

        with pytest.raises((asyncio.CancelledError, RuntimeError)):
            await asyncio.wait_for(
                FFmpegVideoEncoderAction(config).run(ctx),
                timeout=15.0,
            )

        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"Cancellation took too long: {elapsed:.2f}s"

        await canceller
