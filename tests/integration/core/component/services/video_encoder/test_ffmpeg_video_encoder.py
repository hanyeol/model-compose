"""Tests for the FFmpeg video-encoder driver.

Covers:
  - Frames → video encoding (single sequence, batches, streaming input)
  - Existing video passthrough (with optional audio mux)
  - Encoding options (codec / bitrate / resolution / format)
  - Streaming output (opt-in, fallback for non-streamable formats)
  - Error propagation
  - Live-stream inputs: pipe:0 (single stream), pipe:<fd> inheritance (two
    live streams on POSIX), and the spool fallback for non-streamable inputs
  - Cancellation propagation via CancellationToken
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import AsyncIterator
from typing import Any, Callable, List, Optional

import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_encoder.drivers.ffmpeg import (
    FFmpegVideoEncoderAction,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.dsl.schema.action.impl.media import (
    AudioEncoderConfig,
    VideoAudioEncodingConfig,
    VideoEncoderConfig,
)


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_frames(count: int = 8, size=(64, 48), color_fn: Optional[Callable[[int], tuple]] = None) -> List[PILImage.Image]:
    """Produce a list of solid-color RGB frames."""
    def default_color(i: int) -> tuple:
        return (30 + i * 20, 60, 120)

    color_fn = color_fn or default_color
    return [PILImage.new("RGB", size, color_fn(i)) for i in range(count)]


def _make_context(
    frames_value: Any = None,
    video_value: Any = None,
    audio_value: Any = None,
) -> ComponentActionContext:
    """Build a mock ComponentActionContext.

    - `frames_value`: what render_image_array returns (list-of-lists or AsyncIterator)
    - `video_value`: what render_video returns (single/list/AsyncIterator)
    - `audio_value`: what render_audio returns
    """
    from mindor.core.foundation.streaming.video import create_video_source
    from mindor.core.foundation.streaming.audio import create_audio_source

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
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

    def _resolve_video(v):
        if isinstance(v, str):
            with open(v, "rb") as f:
                v = f.read()
        return create_video_source(v)

    def _resolve_audio(a):
        if isinstance(a, str):
            with open(a, "rb") as f:
                a = f.read()
        return create_audio_source(a)

    async def render_image_array(value):
        # `_encode_from_frames` is entered only when the resolved value is
        # (or contains) `ImageArrayValue`. Callers still pass raw lists of
        # PIL images for convenience; wrap them here so the encoder's
        # dispatch in `_process` picks the frames path.
        target = frames_value if frames_value is not None else value
        if callable(target) and not isinstance(target, (list, str)):
            src = target()
            assert isinstance(src, AsyncIterator)

            async def _map():
                async for chunk in src:
                    yield ImageArrayValue(list(chunk))
            return _map()
        # `target` is a list-of-lists of PIL images (one inner list per
        # ImageArrayValue).
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
        target = audio_value if audio_value is not None else value
        if isinstance(target, list):
            return [_resolve_audio(a) for a in target]
        return _resolve_audio(target)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_image_array = AsyncMock(side_effect=render_image_array)
    ctx.render_video = AsyncMock(side_effect=render_video)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


def _make_config(
    *,
    video: Any = None,
    frames: Any = None,
    frame_rate: Any = None,
    audio: Any = None,
    encoding: Optional[VideoAudioEncodingConfig] = None,
    streaming: bool = False,
    batch_size: Any = None,
    output: Any = None,
) -> VideoEncoderActionConfig:
    kwargs = {}
    if video is not None:
        kwargs["video"] = video
    if frames is not None:
        kwargs["frames"] = frames
    if frame_rate is not None:
        kwargs["frame_rate"] = frame_rate
    if audio is not None:
        kwargs["audio"] = audio
    if encoding is not None:
        kwargs["encoding"] = encoding
    if streaming:
        kwargs["streaming"] = streaming
    if batch_size is not None:
        kwargs["batch_size"] = batch_size
    if output is not None:
        kwargs["output"] = output
    return VideoEncoderActionConfig(**kwargs)


@pytest.fixture(scope="module")
def sample_mp4_path():
    """Tiny 2-second mp4 with h264+aac."""
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


@pytest.fixture(scope="module")
def sample_audio_path():
    """Tiny 2-second mp3 sine tone."""
    path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
            "-c:a", "libmp3lame",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _probe_video(path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate",
            "-show_entries", "format=format_name",
            "-of", "default=noprint_wrappers=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    info = {}
    for line in result.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def _probe_audio_codec(path: str) -> str:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


async def _drain_resource_to_file(resource: VideoStreamResource) -> str:
    """Materialize a VideoStreamResource (stream- or file-backed) to a temp file."""
    dest = tempfile.NamedTemporaryFile(
        suffix=f".{resource.format or 'bin'}", delete=False
    ).name

    src = resource.source

    if isinstance(src, FileStreamResource):
        with open(src.path, "rb") as f_in, open(dest, "wb") as f_out:
            f_out.write(f_in.read())
    else:
        with open(dest, "wb") as f_out:
            async for chunk in resource:
                f_out.write(chunk)

    await resource.close()
    return dest


@ffmpeg_required
class TestEncodeFromFrames:
    """Encoding a sequence of PIL frames into a video file."""

    @pytest.mark.anyio
    async def test_frames_to_mp4(self):
        frames = _make_frames(count=12)
        config = _make_config(frames="${prev.frames}", frame_rate=12)
        ctx = _make_context(frames_value=[frames])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], VideoStreamResource)
        assert result[0].format == "mp4"

        out_path = await _drain_resource_to_file(result[0])
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
            assert int(info["width"]) == 64
            assert int(info["height"]) == 48
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_frames_with_audio_mux(self, sample_audio_path):
        frames = _make_frames(count=24)  # 2 seconds at 12 fps
        config = _make_config(
            frames="${prev.frames}",
            frame_rate=12,
            audio="${input.audio}",
        )
        ctx = _make_context(
            frames_value=[frames],
            audio_value=sample_audio_path,
        )

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result[0])
        try:
            assert _probe_audio_codec(out_path) == "aac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_frames_batch_encoding(self):
        seq_a = _make_frames(count=6, color_fn=lambda i: (255, 0, 0))
        seq_b = _make_frames(count=6, color_fn=lambda i: (0, 255, 0))
        config = _make_config(frames="${frames}", frame_rate=6)
        ctx = _make_context(frames_value=[seq_a, seq_b])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, VideoStreamResource)
            await item.close()

    @pytest.mark.anyio
    async def test_frames_stream_input(self):
        def _make_iter():
            async def _gen():
                yield _make_frames(count=4)
                yield _make_frames(count=4)
            return _gen()

        config = _make_config(frames="${stream}", frame_rate=12)
        ctx = _make_context(frames_value=_make_iter)

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        for item in items:
            assert isinstance(item, VideoStreamResource)
            await item.close()


@ffmpeg_required
class TestEncodeFromVideo:
    """Encoding/muxing existing video sources."""

    @pytest.mark.anyio
    async def test_video_passthrough(self, sample_mp4_path):
        config = _make_config(video="${prev.video}")
        ctx = _make_context(video_value=sample_mp4_path)

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, VideoStreamResource)
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_video_with_audio_mux(self, sample_mp4_path, sample_audio_path):
        """Existing video + separate audio track → muxed output.
        The output uses the newly muxed audio track."""
        config = _make_config(
            video="${prev.video}",
            audio="${input.audio}",
        )
        ctx = _make_context(
            video_value=sample_mp4_path,
            audio_value=sample_audio_path,
        )

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result)
        try:
            assert _probe_audio_codec(out_path) == "aac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_video_list_input(self, sample_mp4_path):
        config = _make_config(video="${videos}")
        ctx = _make_context(video_value=[sample_mp4_path, sample_mp4_path])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, VideoStreamResource)
            await item.close()


@ffmpeg_required
class TestEncodingOptions:
    """Custom codec / resolution / format overrides."""

    @pytest.mark.anyio
    async def test_webm_format(self):
        frames = _make_frames(count=6)
        config = _make_config(
            frames="${f}",
            frame_rate=6,
            encoding=VideoAudioEncodingConfig(format="webm"),
        )
        ctx = _make_context(frames_value=[frames])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert result[0].format == "webm"
        out_path = await _drain_resource_to_file(result[0])
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "vp9"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_resolution_override(self):
        frames = _make_frames(count=6)
        config = _make_config(
            frames="${f}",
            frame_rate=6,
            encoding=VideoAudioEncodingConfig(
                format="mp4",
                video=VideoEncoderConfig(resolution="128x96"),
            ),
        )
        ctx = _make_context(frames_value=[frames])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result[0])
        try:
            info = _probe_video(out_path)
            assert int(info["width"]) == 128
            assert int(info["height"]) == 96
        finally:
            os.unlink(out_path)


@ffmpeg_required
class TestStreamingOutput:
    """Explicit `streaming: true` opts into stdout pipe (streamable formats only)."""

    @pytest.mark.anyio
    async def test_streaming_webm_returns_pipe_backed_resource(self):
        frames = _make_frames(count=6)
        config = _make_config(
            frames="${f}",
            frame_rate=6,
            encoding=VideoAudioEncodingConfig(format="webm"),
            streaming=True,
        )
        ctx = _make_context(frames_value=[frames])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert result[0].format == "webm"
        # Streamable output: source is NOT a FileStreamResource
        assert not isinstance(result[0].source, FileStreamResource)

        out_path = await _drain_resource_to_file(result[0])
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "vp9"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_streaming_mp4_falls_back_to_file(self):
        frames = _make_frames(count=6)
        config = _make_config(
            frames="${f}",
            frame_rate=6,
            encoding=VideoAudioEncodingConfig(format="mp4"),
            streaming=True,
        )
        ctx = _make_context(frames_value=[frames])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        # mp4 is not streamable → falls back to file output (warning logged)
        assert isinstance(result[0].source, FileStreamResource)
        await result[0].close()


@ffmpeg_required
class TestErrorPropagation:
    @pytest.mark.anyio
    async def test_invalid_video_input_raises(self, tmp_path):
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"definitely not a video" * 32)

        config = _make_config(video="${v}")
        ctx = _make_context(video_value=str(bogus))

        with pytest.raises(RuntimeError, match="ffmpeg video encoding failed"):
            await FFmpegVideoEncoderAction(config).run(ctx)


@ffmpeg_required
class TestOutputTemplate:
    @pytest.mark.anyio
    async def test_output_template_overrides_return_value(self):
        frames = _make_frames(count=6)
        config = _make_config(
            frames="${f}",
            frame_rate=6,
            output="encoded",
        )
        ctx = _make_context(frames_value=[frames])

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert result == "encoded"
        registered = dict(c.args for c in ctx.register_source.call_args_list)
        assert "result" in registered
        # Registered result is a list (frames path always produces list results)
        for item in registered["result"]:
            await item.close()


# ---------------------------------------------------------------------------
# Live-stream input helpers
#
# The default `_make_context` helpers route bytes through `create_video_source`
# / `create_audio_source`, which build a MediaSource *without* setting the
# `format` field. That drops us into the spool path in `_resolve_input_path`
# because the streamable check needs a format string. For the tests below we
# want to exercise pipe:0 and pipe:<fd>, so we build MediaSources directly and
# hand them to the render mocks.
# ---------------------------------------------------------------------------

def _sample_mpegts_bytes() -> bytes:
    """Build a tiny mpegts video clip in memory (streamable input format)."""
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=12",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mpegts", "pipe:1",
        ],
        capture_output=True, check=True,
    )
    return proc.stdout


def _sample_mp3_bytes() -> bytes:
    """Build a tiny mp3 audio clip in memory (streamable input format)."""
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-c:a", "libmp3lame", "-f", "mp3", "pipe:1",
        ],
        capture_output=True, check=True,
    )
    return proc.stdout


def _make_context_with_media(
    video: Optional[MediaSource] = None,
    audio: Optional[MediaSource] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> ComponentActionContext:
    """A context whose render_video / render_audio return the given MediaSource verbatim.

    This bypasses `create_video_source(bytes)` which drops the `format` hint
    and therefore forces the spool path. We need to keep the format so the
    encoder actually exercises pipe:0 / pipe:<fd>.
    """
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = cancellation_token

    sources: dict = {}
    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if value == "${result}":
            return sources.get("result")
        return value

    async def render_video(value):
        return video

    async def render_audio(value):
        return audio

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


@pytest.fixture(scope="module")
def sample_mpegts_bytes():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available on PATH")
    return _sample_mpegts_bytes()


@pytest.fixture(scope="module")
def sample_mp3_bytes():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available on PATH")
    return _sample_mp3_bytes()


@ffmpeg_required
class TestLiveStreamInputs:
    """Exercise the pipe:0 / pipe:<fd> / spool branches of _resolve_input_path
    and _resolve_input_source with real ffmpeg processes."""

    @pytest.mark.anyio
    async def test_streamable_video_uses_pipe(self, sample_mpegts_bytes):
        """A streamable input format (mpegts) is fed on stdin — no temp file."""
        video = MediaSource(BytesStreamResource(sample_mpegts_bytes), format="mpegts")

        config = _make_config(video="${v}")
        ctx = _make_context_with_media(video=video)

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, VideoStreamResource)
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            # Encoding succeeded and produced a real h264 stream.
            assert info["codec_name"] == "h264"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_non_streamable_video_spools(self, sample_mp4_path):
        """Non-streamable in-memory input (mp4 bytes) has to be spooled to disk."""
        with open(sample_mp4_path, "rb") as f:
            mp4_bytes = f.read()
        video = MediaSource(BytesStreamResource(mp4_bytes), format="mp4")

        config = _make_config(video="${v}")
        ctx = _make_context_with_media(video=video)

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        assert isinstance(result, VideoStreamResource)
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_dual_live_streams_use_fd_inheritance(
        self, sample_mpegts_bytes, sample_mp3_bytes,
    ):
        """Two live streams: video on pipe:0, audio on pipe:<fd>.

        Without fd inheritance the audio side would be spooled to a temp file
        first; here we expect neither side to touch disk, and the resulting
        output must contain both tracks.
        """
        if os.name != "posix":
            pytest.skip("fd inheritance is POSIX-only")

        video = MediaSource(BytesStreamResource(sample_mpegts_bytes), format="mpegts")
        audio = MediaSource(BytesStreamResource(sample_mp3_bytes), format="mp3")

        config = _make_config(video="${v}", audio="${a}")
        ctx = _make_context_with_media(video=video, audio=audio)

        result = await FFmpegVideoEncoderAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
            # The replacement audio track survived: expect aac (default codec).
            assert _probe_audio_codec(out_path) == "aac"
        finally:
            os.unlink(out_path)


class _SlowMpegtsStream(BytesStreamResource):
    """An mpegts source that keeps yielding chunks slowly and never ends so
    ffmpeg stays busy long enough for the cancellation token to fire."""

    def __init__(self, data: bytes, chunk_delay_s: float = 0.02, max_repeats: int = 200):
        super().__init__(data, chunk_size=4096)
        self._chunk_delay_s = chunk_delay_s
        self._max_repeats = max_repeats

    async def _iterate_stream(self):
        # Loop the same mpegts payload many times with sleeps in between so
        # the resulting encode runs for several seconds. If we ever exhaust
        # the loop the test would time out — max_repeats is a safety upper
        # bound, not the expected exit path.
        for _ in range(self._max_repeats):
            offset = 0
            while offset < len(self.data):
                chunk = self.data[offset : offset + self.chunk_size]
                offset += self.chunk_size
                await asyncio.sleep(self._chunk_delay_s)
                yield chunk


@ffmpeg_required
class TestCancellation:
    """CancellationToken should reach the running ffmpeg process and end it."""

    @pytest.mark.anyio
    async def test_cancellation_token_stops_encoding(self, sample_mpegts_bytes):
        """Cancelling the token mid-run causes the encoder to raise
        CancelledError instead of returning a completed VideoStreamResource."""
        token = CancellationToken()

        # Feed ffmpeg a drip-fed mpegts stream so the encode is guaranteed to
        # still be running by the time the cancel fires (the watcher polls
        # every 0.2s).
        video = MediaSource(_SlowMpegtsStream(sample_mpegts_bytes), format="mpegts")

        config = _make_config(video="${v}")
        ctx = _make_context_with_media(video=video, cancellation_token=token)

        async def _cancel_soon() -> None:
            await asyncio.sleep(0.3)
            token.cancel(reason="test")

        encode_task = asyncio.create_task(
            FFmpegVideoEncoderAction(config).run(ctx)
        )
        canceller = asyncio.create_task(_cancel_soon())

        with pytest.raises((asyncio.CancelledError, RuntimeError)):
            await encode_task
        await canceller
