"""Unit tests for what the rtmp-publisher ffmpeg driver lets into logs and errors.

An RTMP ingest URL holds the stream key, and a publish can run for days, so a
failure message must neither carry the key nor grow with the publish length.
"""

from __future__ import annotations

import asyncio

import pytest

from mindor.core.component.services.rtmp_publisher.drivers.ffmpeg import (
    FFmpegRtmpPublisher,
    _read_stderr_tail,
    _redact_url,
)
from mindor.core.foundation.media.encoding import (
    AudioEncoderParams,
    VideoAudioEncodingParams,
    VideoEncoderParams,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestRedactUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            (
                "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop-qrst",
                "rtmp://a.rtmp.youtube.com/live2/<redacted>",
            ),
            (
                "rtmps://a.rtmps.youtube.com:443/live2/abcd-efgh-ijkl-mnop-qrst",
                "rtmps://a.rtmps.youtube.com:443/live2/<redacted>",
            ),
            (
                "rtmp://live.twitch.tv/app/live_123456_AbCdEf",
                "rtmp://live.twitch.tv/app/<redacted>",
            ),
            (
                "rtmps://live-api-s.facebook.com:443/rtmp/FB-1-0-Ab?s_bl=1&s_sc=2&a=Token",
                "rtmps://live-api-s.facebook.com:443/rtmp/<redacted>?<redacted>",
            ),
            (
                "rtmp://user:hunter2@ingest.example.com/live/key123",
                "rtmp://user:<redacted>@ingest.example.com/live/<redacted>",
            ),
        ],
    )
    def test_secrets_are_masked(self, url, expected):
        assert _redact_url(url) == expected

    def test_url_without_stream_key_is_unchanged(self):
        assert _redact_url("rtmp://localhost/live") == "rtmp://localhost/live"
        assert _redact_url("rtmp://localhost/live/") == "rtmp://localhost/live/"

    def test_file_path_endpoint_is_unchanged(self):
        assert _redact_url("/tmp/out.flv") == "/tmp/out.flv"


class TestStderrTail:
    @pytest.mark.anyio
    async def test_keeps_only_the_last_lines(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b"".join(f"line {i}\n".encode() for i in range(1000)))
        reader.feed_eof()

        tail = await _read_stderr_tail(reader)

        assert tail.splitlines() == [f"line {i}" for i in range(980, 1000)]

    @pytest.mark.anyio
    async def test_empty_stderr(self):
        reader = asyncio.StreamReader()
        reader.feed_eof()

        assert await _read_stderr_tail(reader) == ""


class TestPublishCommandLogging:
    def test_progress_stats_are_off(self):
        # Progress lines are '\r'-terminated, so they would pile up into one
        # ever-growing stderr "line" for the whole publish.
        encoding = VideoAudioEncodingParams(
            format="flv",
            video=VideoEncoderParams(codec="libx264"),
            audio=AudioEncoderParams(codec="aac"),
        )
        publisher = FFmpegRtmpPublisher(url="rtmp://localhost/live/key", encoding=encoding)

        command = publisher._build_publish_command("pipe:0", None, None, None, None)

        assert "-nostats" in command
        assert command[command.index("-loglevel") + 1] == "warning"
