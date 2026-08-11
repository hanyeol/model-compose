"""Integration tests for FFmpegRtmpPublisher.

The publisher writes to `self.url` via `-f <format> <url>`, so any local
filesystem path works as an "endpoint" — no real RTMP server needed. The
tests here exercise the input side (file / pipe:0 / pipe:<fd>) and the
cancellation path against real ffmpeg processes; RTMP protocol conformance
is out of scope.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from typing import Optional

import pytest

from mindor.core.component.services.rtmp_publisher.drivers.ffmpeg import (
    FFmpegRtmpPublisher,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _default_encoding() -> "VideoAudioEncodingParams":
    """Rendered encoding params matching the driver's flv/h264/aac defaults."""
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
    """Tiny 1-second mp4 with h264 + aac."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available on PATH")
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
def sample_mpegts_bytes():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available on PATH")
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=12",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mpegts", "pipe:1",
        ],
        capture_output=True, check=True,
    )
    return proc.stdout


@pytest.fixture(scope="module")
def sample_mp3_bytes():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available on PATH")
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-c:a", "libmp3lame", "-f", "mp3", "pipe:1",
        ],
        capture_output=True, check=True,
    )
    return proc.stdout


def _probe_video_codec(path: str) -> str:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


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


class _SlowMpegtsStream(BytesStreamResource):
    """Drip-feeds mpegts bytes forever so a publish stays busy while a
    CancellationToken fires."""

    def __init__(self, data: bytes, chunk_delay_s: float = 0.02, max_repeats: int = 200):
        super().__init__(data, chunk_size=4096)
        self._chunk_delay_s = chunk_delay_s
        self._max_repeats = max_repeats

    async def _iterate_stream(self):
        for _ in range(self._max_repeats):
            offset = 0
            while offset < len(self.data):
                chunk = self.data[offset : offset + self.chunk_size]
                offset += self.chunk_size
                await asyncio.sleep(self._chunk_delay_s)
                yield chunk


@ffmpeg_required
class TestPublisherInputs:
    """Exercise the file / pipe:0 / pipe:<fd> input paths against real ffmpeg."""

    @pytest.mark.anyio
    async def test_video_file_publishes_to_flv(self, sample_mp4_path, tmp_path):
        out = tmp_path / "out.flv"
        publisher = FFmpegRtmpPublisher(url=str(out), encoding=_default_encoding())

        await publisher.publish(
            video=sample_mp4_path,
            video_attrs=None,
            audio=None,
            audio_format=None,
            audio_attrs=None,
        )

        assert out.exists() and out.stat().st_size > 0
        assert _probe_video_codec(str(out)) == "h264"

    @pytest.mark.anyio
    async def test_streamable_video_uses_pipe(self, sample_mpegts_bytes, tmp_path):
        out = tmp_path / "out.flv"
        publisher = FFmpegRtmpPublisher(url=str(out), encoding=_default_encoding())

        video = MediaSource(BytesStreamResource(sample_mpegts_bytes), format="mpegts")

        await publisher.publish(
            video=video,
            video_attrs=None,
            audio=None,
            audio_format=None,
            audio_attrs=None,
        )

        assert out.exists() and out.stat().st_size > 0
        assert _probe_video_codec(str(out)) == "h264"

    @pytest.mark.anyio
    async def test_dual_live_streams_use_fd_inheritance(
        self, sample_mpegts_bytes, sample_mp3_bytes, tmp_path
    ):
        """Video on pipe:0, audio on pipe:<fd> — the muxed flv should carry
        both tracks. If fd inheritance were broken the audio side would end
        up empty or the publish would time out."""
        if os.name != "posix":
            pytest.skip("fd inheritance is POSIX-only")

        out = tmp_path / "out.flv"
        publisher = FFmpegRtmpPublisher(url=str(out), encoding=_default_encoding())

        video = MediaSource(BytesStreamResource(sample_mpegts_bytes), format="mpegts")
        audio = MediaSource(BytesStreamResource(sample_mp3_bytes), format="mp3")

        await publisher.publish(
            video=video,
            video_attrs=None,
            audio=audio,
            audio_format="mp3",
            audio_attrs=None,
        )

        assert out.exists() and out.stat().st_size > 0
        assert _probe_video_codec(str(out)) == "h264"
        # AAC is the codec we asked for in `_default_params`, the replacement
        # audio should survive the mux.
        assert _probe_audio_codec(str(out)) == "aac"


@ffmpeg_required
class TestPublisherCancellation:
    @pytest.mark.anyio
    async def test_cancellation_token_stops_publish(
        self, sample_mpegts_bytes, tmp_path
    ):
        """Firing the token mid-publish surfaces CancelledError instead of
        letting ffmpeg run to completion."""
        out = tmp_path / "out.flv"
        publisher = FFmpegRtmpPublisher(url=str(out), encoding=_default_encoding())

        video = MediaSource(_SlowMpegtsStream(sample_mpegts_bytes), format="mpegts")

        token = CancellationToken()

        async def _cancel_soon() -> None:
            await asyncio.sleep(0.3)
            token.cancel(reason="test")

        publish_task = asyncio.create_task(publisher.publish(
            video=video,
            video_attrs=None,
            audio=None,
            audio_format=None,
            audio_attrs=None,
            cancellation_token=token,
        ))
        canceller = asyncio.create_task(_cancel_soon())

        with pytest.raises((asyncio.CancelledError, RuntimeError)):
            await publish_task
        await canceller
