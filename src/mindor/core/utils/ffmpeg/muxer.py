from __future__ import annotations

from typing import Dict

# ffmpeg picks the output muxer from a filename's extension, but ffprobe
# reports containers by muxer name — some of those (e.g. `matroska`) aren't
# valid filename extensions. Map muxer-only names to the extension ffmpeg
# will autodetect.
_MUXER_EXTENSION_MAP: Dict[str, str] = {
    "matroska": "mkv",
    "mpegts":   "ts",
    "mpeg":     "mpg",
    "asf":      "wmv",
}

def get_extension_for_muxer(muxer: str) -> str:
    """Convert an ffmpeg muxer name to a filename extension ffmpeg autodetects."""
    return _MUXER_EXTENSION_MAP.get(muxer, muxer)
