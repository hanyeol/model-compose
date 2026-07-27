"""Async / non-blocking tests for the FFmpeg video-converter driver.

Complements the existing behavioral tests by verifying:
  - `Action.run(context)` yields the event loop while ffmpeg runs (non-blocking).
  - `Service._run(action, context)` has no `loop` kwarg after the refactor.
  - Batch inputs execute end-to-end.
  - A CancellationToken fired mid-run terminates the operation promptly.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import shutil
import subprocess
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_converter.base import VideoConverterService
from mindor.core.component.services.video_converter.drivers.ffmpeg import (
    FFmpegVideoConverterAction,
    FFmpegVideoConverterService,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.dsl.schema.action import VideoConverterActionConfig
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


@pytest.fixture(scope="module")
def sample_mp4_path():
    """Small ~2s mp4 — long enough to give the ticker time to accumulate ticks."""
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


def _make_context(video_value: Any, *, cancellation_token=None) -> ComponentActionContext:
    from mindor.core.foundation.streaming.video import create_video_source
    from collections.abc import AsyncIterator as _AI

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
            if value == "${result[]}":
                return sources.get("result[]")
        return value

    def resolve_one(value):
        if isinstance(value, str):
            with open(value, "rb") as f:
                value = f.read()
        return create_video_source(value)

    async def render_video(value):
        if callable(video_value) and not isinstance(video_value, str):
            src = video_value()
            assert isinstance(src, _AI)

            async def _map():
                async for item in src:
                    yield resolve_one(item)
            return _map()
        if isinstance(video_value, list):
            return [resolve_one(v) for v in video_value]
        return resolve_one(video_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


def _make_config(**kwargs) -> VideoConverterActionConfig:
    encoding = VideoAudioEncodingConfig(
        format="mp4",
        video=VideoEncoderConfig(codec="libx264"),
        audio=AudioEncoderConfig(codec="aac"),
    )
    kwargs.setdefault("video", "<placeholder>")
    kwargs.setdefault("encoding", encoding)
    return VideoConverterActionConfig(**kwargs)


@ffmpeg_required
class TestFFmpegVideoConverterAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self, sample_mp4_path):
        """Wall time of conversion is dominated by ffmpeg; ticker must keep firing."""
        config = _make_config()
        ctx = _make_context(sample_mp4_path)

        result = await assert_does_not_block(
            FFmpegVideoConverterAction(config).run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, VideoStreamResource)
        assert result.format == "mp4"
        # Drain / close to release the underlying temp file.
        if isinstance(result.source, FileStreamResource):
            await result.close()
        else:
            async for _ in result:
                pass
            await result.close()

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_mp4_path):
        """After the refactor, `Service._run` takes (action, context) only — no `loop`."""
        # Signature inspection.
        sig = inspect.signature(FFmpegVideoConverterService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )
        # Positive-run call: no TypeError should surface.
        service = FFmpegVideoConverterService.__new__(FFmpegVideoConverterService)
        VideoConverterService.__init__(service, "vc", MagicMock(), False)

        ctx = _make_context(sample_mp4_path)
        result = await service._run(_make_config(), ctx)
        assert isinstance(result, VideoStreamResource)
        await result.close()

    @pytest.mark.anyio
    async def test_batch_input_processes_each(self, sample_mp4_path):
        """A list of 2 sources should return a list of 2 VideoStreamResources."""
        config = _make_config()
        ctx = _make_context([sample_mp4_path, sample_mp4_path])

        result = await assert_does_not_block(
            FFmpegVideoConverterAction(config).run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, VideoStreamResource)
            await item.close()

    @pytest.mark.anyio
    async def test_cancellation_token_stops_conversion_promptly(self, tmp_path):
        """Firing the cancellation token mid-run must abort ffmpeg before completion."""
        # Build a 10-second source so cancellation can bite well before natural EOF.
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
        ctx = _make_context(long_source, cancellation_token=token)

        # mp4 output uses `_convert_to_file`, which awaits ffmpeg to completion
        # and honors the cancellation token via its polling watcher.
        # vp9 keeps encoding CPU-heavy so ffmpeg is still busy when we cancel.
        config = VideoConverterActionConfig(
            video="<placeholder>",
            encoding=VideoAudioEncodingConfig(
                format="mp4",
                video=VideoEncoderConfig(codec="libx264"),
                audio=AudioEncoderConfig(codec="aac"),
            ),
        )

        async def _cancel_soon():
            await asyncio.sleep(0.2)
            token.cancel(reason="test")

        canceller = asyncio.create_task(_cancel_soon())
        import time
        started = time.monotonic()

        with pytest.raises((asyncio.CancelledError, RuntimeError)):
            await asyncio.wait_for(
                FFmpegVideoConverterAction(config).run(ctx),
                timeout=15.0,
            )

        elapsed = time.monotonic() - started
        # Should exit well before the full 10s ffmpeg run.
        assert elapsed < 5.0, f"Cancellation took too long: {elapsed:.2f}s"

        await canceller
