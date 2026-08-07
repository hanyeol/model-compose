from __future__ import annotations

from typing import Optional, Set

# Video/media container formats that ffmpeg can decode straight off pipe:0
# without seeking. Formats like mp4/mov/mkv/avi keep their moov atom or cue
# index at the end and must be spooled to a file.
_STREAMABLE_VIDEO_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

def is_streamable_video_format(format: Optional[str]) -> bool:
    """True if the video format can be fed to ffmpeg's pipe:0 without seeking."""
    return format in _STREAMABLE_VIDEO_FORMATS
