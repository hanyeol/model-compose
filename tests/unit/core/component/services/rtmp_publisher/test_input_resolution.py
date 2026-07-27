"""Unit tests for the rtmp-publisher ffmpeg driver's input resolution helpers.

The publisher decides how each MediaSource reaches ffmpeg — file path, stdin
`pipe:0`, or an inherited descriptor `pipe:<fd>`.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from mindor.core.component.services.rtmp_publisher.drivers import ffmpeg as publisher_ffmpeg
from mindor.core.component.services.rtmp_publisher.drivers.ffmpeg import (
    FFmpegRtmpPublisher,
    FFmpegRtmpPublisherAction,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.channels.subprocess_stream import SubprocessStreamChannel


def _bytes_media(data: bytes = b"", format: Optional[str] = None) -> MediaSource:
    return MediaSource(stream=BytesStreamResource(data), format=format)


def _file_media(path: str, format: Optional[str] = None) -> MediaSource:
    return MediaSource(stream=FileStreamResource(path), format=format)


class TestPublisherResolveInputSource:
    """`_resolve_input_source` picks between file path, `pipe:0`, and `pipe:<fd>`."""

    def test_file_path_passes_through(self):
        fd_channels: List[SubprocessStreamChannel] = []
        spec, stdin_owner = FFmpegRtmpPublisher._resolve_input_source(
            "/tmp/x.mp4", stdin_owner=None, fd_channels=fd_channels
        )
        assert spec == "/tmp/x.mp4"
        assert stdin_owner is None
        assert fd_channels == []

    def test_first_live_stream_claims_stdin(self):
        media = _bytes_media(format="mpegts")
        fd_channels: List[SubprocessStreamChannel] = []
        spec, stdin_owner = FFmpegRtmpPublisher._resolve_input_source(
            media, stdin_owner=None, fd_channels=fd_channels
        )
        assert spec == "pipe:0"
        assert stdin_owner is media
        assert fd_channels == []

    def test_second_live_stream_gets_fd(self, monkeypatch: pytest.MonkeyPatch):
        # On POSIX the second live stream is fed over an inherited descriptor.
        monkeypatch.setattr(publisher_ffmpeg, "_SUPPORTS_FD_INPUT", True)

        first = _bytes_media(format="mpegts")
        second = _bytes_media(format="mp3")
        fd_channels: List[SubprocessStreamChannel] = []

        try:
            _, stdin_owner = FFmpegRtmpPublisher._resolve_input_source(
                first, stdin_owner=None, fd_channels=fd_channels
            )
            spec, updated_owner = FFmpegRtmpPublisher._resolve_input_source(
                second, stdin_owner=stdin_owner, fd_channels=fd_channels
            )

            assert spec.startswith("pipe:")
            assert spec != "pipe:0"
            # stdin_owner remains the first stream — it's the one on pipe:0.
            assert updated_owner is first
            assert len(fd_channels) == 1
        finally:
            for channel in fd_channels:
                asyncio.run(channel.close())

    def test_second_live_stream_raises_on_windows(self, monkeypatch: pytest.MonkeyPatch):
        # Windows can't pass an extra descriptor to a child, so the caller
        # must have spooled one side before reaching here.
        monkeypatch.setattr(publisher_ffmpeg, "_SUPPORTS_FD_INPUT", False)

        first = _bytes_media(format="mpegts")
        second = _bytes_media(format="mp3")
        fd_channels: List[SubprocessStreamChannel] = []

        _, stdin_owner = FFmpegRtmpPublisher._resolve_input_source(
            first, stdin_owner=None, fd_channels=fd_channels
        )

        with pytest.raises(RuntimeError, match="Multiple live streams"):
            FFmpegRtmpPublisher._resolve_input_source(
                second, stdin_owner=stdin_owner, fd_channels=fd_channels
            )

        assert len(fd_channels) == 0


class TestActionResolveInputPath:
    """`Action._resolve_input_path` picks between three input strategies."""

    def _action(self) -> FFmpegRtmpPublisherAction:
        # Bypass __init__ because it wants a full ActionConfig; the method
        # under test doesn't touch self.
        return FFmpegRtmpPublisherAction.__new__(FFmpegRtmpPublisherAction)

    def test_file_stream_resource_returns_path(self, tmp_path):
        real_path = tmp_path / "clip.mp4"
        real_path.write_bytes(b"")

        media = _file_media(str(real_path), format="mp4")
        path, spooled = asyncio.run(self._action()._resolve_input_path(media))
        assert path == str(real_path)
        assert spooled is False

    def test_streamable_format_uses_pipe(self):
        media = _bytes_media(b"\x47\x40\x00\x10", format="mpegts")
        path, spooled = asyncio.run(self._action()._resolve_input_path(media))
        assert path is None
        assert spooled is False

    def test_streamable_format_is_case_sensitive(self):
        """Format matching is case-sensitive; upper-case variants fall through to spooling."""
        media = _bytes_media(b"", format="MPEGTS")
        path, spooled = asyncio.run(self._action()._resolve_input_path(media))
        assert path is not None
        assert spooled is True

    def test_non_streamable_format_spools(self, monkeypatch: pytest.MonkeyPatch):
        recorded: List[tuple] = []

        async def fake_spool(stream, format):
            recorded.append((stream, format))
            return "/tmp/spooled.mp4"

        monkeypatch.setattr(publisher_ffmpeg, "save_stream_to_temporary_file", fake_spool)

        media = _bytes_media(b"", format="mp4")
        path, spooled = asyncio.run(self._action()._resolve_input_path(media))

        assert path == "/tmp/spooled.mp4"
        assert spooled is True
        assert len(recorded) == 1
        assert recorded[0][1] == "mp4"
