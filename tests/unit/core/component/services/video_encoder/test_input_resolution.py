"""Unit tests for the video-encoder ffmpeg driver's input resolution helpers.

These functions decide how each MediaSource reaches ffmpeg: as a file path,
as `pipe:0` on stdin, or as `pipe:<fd>` on an inherited descriptor. The
rules matter because getting them wrong either force-spools live streams
(latency) or hands ffmpeg an unreadable input (silent failure).
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from mindor.core.component.action import media as action_media
from mindor.core.component.action.media import MediaInputPathResolver
from mindor.core.component.services.video_encoder.drivers import ffmpeg as encoder_ffmpeg
from mindor.core.component.services.video_encoder.drivers.ffmpeg import FFmpegVideoEncoderAction
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.channels.subprocess_stream import SubprocessStreamChannel


def _bytes_media(data: bytes = b"", format: Optional[str] = None) -> MediaSource:
    """A MediaSource backed by an in-memory byte buffer (not a file)."""
    return MediaSource(stream=BytesStreamResource(data), format=format)


def _file_media(path: str, format: Optional[str] = None) -> MediaSource:
    """A MediaSource whose stream is already a real file — no spooling needed."""
    return MediaSource(stream=FileStreamResource(path), format=format)


class TestMediaInputPathResolver:
    """``MediaInputPathResolver.resolve`` picks between three input strategies."""

    def test_file_stream_resource_returns_path(self, tmp_path):
        # FileStreamResource stat()s the file at construction so we need a
        # real path — an empty temp file is enough for this branch.
        real_path = tmp_path / "movie.mp4"
        real_path.write_bytes(b"")

        media = _file_media(str(real_path), format="mp4")
        path, spooled = asyncio.run(MediaInputPathResolver().resolve(media, streamable_media=[ "video", "audio" ]))
        assert path == str(real_path)
        assert spooled is False

    def test_streamable_format_uses_pipe(self):
        # mpegts is streamable — ffmpeg can consume it from pipe:0 without seek.
        media = _bytes_media(b"\x47\x40\x00\x10", format="mpegts")
        path, spooled = asyncio.run(MediaInputPathResolver().resolve(media, streamable_media=[ "video", "audio" ]))
        assert path is None
        assert spooled is False

    def test_streamable_format_is_case_sensitive(self):
        """Format matching is case-sensitive; upper-case variants fall through to spooling."""
        media = _bytes_media(b"", format="MPEGTS")
        path, spooled = asyncio.run(MediaInputPathResolver().resolve(media, streamable_media=[ "video", "audio" ]))
        assert path is not None
        assert spooled is True

    def test_non_streamable_format_spools(self, monkeypatch: pytest.MonkeyPatch):
        # mp4 needs seek for moov, so it should be spooled to a temp file.
        # We stub the spooler to keep the test hermetic.
        recorded: List[tuple] = []

        async def fake_spool(stream, format):
            recorded.append((stream, format))
            return "/tmp/spooled.mp4"

        monkeypatch.setattr(action_media, "save_stream_to_temporary_file", fake_spool)

        media = _bytes_media(b"", format="mp4")
        path, spooled = asyncio.run(MediaInputPathResolver().resolve(media, streamable_media=[ "video", "audio" ]))

        assert path == "/tmp/spooled.mp4"
        assert spooled is True
        assert len(recorded) == 1
        assert recorded[0][1] == "mp4"

    def test_unknown_format_spools(self, monkeypatch: pytest.MonkeyPatch):
        # When we don't know the format we can't assume ffmpeg will demux from
        # a pipe — safer to spool so it can seek.
        async def fake_spool(stream, format):
            return "/tmp/spooled.bin"

        monkeypatch.setattr(action_media, "save_stream_to_temporary_file", fake_spool)

        media = _bytes_media(b"", format=None)
        path, spooled = asyncio.run(MediaInputPathResolver().resolve(media, streamable_media=[ "video", "audio" ]))

        assert path == "/tmp/spooled.bin"
        assert spooled is True


class TestResolveInputSource:
    """`_resolve_input_source` distributes inputs across `pipe:0` and inherited fds.

    Contract: the first live MediaSource claims `pipe:0` (returned as the
    updated `stdin_owner`); the second lands on an inherited descriptor when
    the platform supports it (`_SUPPORTS_FD_INPUT`), otherwise it must raise
    so the caller knows to spool one side.
    """

    def test_file_path_passes_through(self):
        # If `_resolve_input_path` already gave us a path, `stdin_owner` is
        # untouched and the input spec is just that path.
        media = _bytes_media()
        fd_channels: List[SubprocessStreamChannel] = []
        spec, stdin_owner = FFmpegVideoEncoderAction._resolve_input_source(
            media,
            media_path="/tmp/x.mp4",
            stdin_owner=None,
            fd_channels=fd_channels,
        )
        assert spec == "/tmp/x.mp4"
        assert stdin_owner is None
        assert fd_channels == []

    def test_first_live_stream_claims_stdin(self):
        media = _bytes_media(format="mpegts")
        fd_channels: List[SubprocessStreamChannel] = []
        spec, stdin_owner = FFmpegVideoEncoderAction._resolve_input_source(
            media,
            media_path=None,
            stdin_owner=None,
            fd_channels=fd_channels,
        )
        assert spec == "pipe:0"
        assert stdin_owner is media
        assert fd_channels == []

    def test_second_live_stream_gets_fd(self, monkeypatch: pytest.MonkeyPatch):
        # On POSIX the second live stream is fed over an inherited descriptor.
        monkeypatch.setattr(encoder_ffmpeg, "_SUPPORTS_FD_INPUT", True)

        first = _bytes_media(format="mpegts")
        second = _bytes_media(format="mp3")
        fd_channels: List[SubprocessStreamChannel] = []

        try:
            _, stdin_owner = FFmpegVideoEncoderAction._resolve_input_source(
                first, media_path=None, stdin_owner=None, fd_channels=fd_channels
            )
            spec, updated_owner = FFmpegVideoEncoderAction._resolve_input_source(
                second, media_path=None, stdin_owner=stdin_owner, fd_channels=fd_channels
            )

            assert spec.startswith("pipe:")
            assert spec != "pipe:0"  # the fd number is variable but never 0
            # stdin_owner stays with the first stream — it's the one on pipe:0.
            assert updated_owner is first
            assert len(fd_channels) == 1
        finally:
            # Release the OS pipe fds the channel opened at construction so
            # the test process doesn't leak them across the suite.
            for channel in fd_channels:
                asyncio.run(channel.close())

    def test_second_live_stream_raises_on_windows(self, monkeypatch: pytest.MonkeyPatch):
        # Windows can't pass an extra descriptor to a child, so the caller
        # must have spooled one side before reaching here.
        monkeypatch.setattr(encoder_ffmpeg, "_SUPPORTS_FD_INPUT", False)

        first = _bytes_media(format="mpegts")
        second = _bytes_media(format="mp3")
        fd_channels: List[SubprocessStreamChannel] = []

        _, stdin_owner = FFmpegVideoEncoderAction._resolve_input_source(
            first, media_path=None, stdin_owner=None, fd_channels=fd_channels
        )

        with pytest.raises(RuntimeError, match="Multiple live streams"):
            FFmpegVideoEncoderAction._resolve_input_source(
                second, media_path=None, stdin_owner=stdin_owner, fd_channels=fd_channels
            )

        # The second call should not have opened a channel on the raise path.
        assert len(fd_channels) == 0
