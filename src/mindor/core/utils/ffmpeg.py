from __future__ import annotations

from typing import Dict

from .shell import run_command
import json

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

async def probe_container_format(input_path: str) -> str:
    """Return a container format name usable by ffmpeg's `-f` flag, via ffprobe."""
    command = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", input_path,
    ]

    stdout, _, returncode = await run_command(command)

    if returncode != 0:
        raise RuntimeError(f"ffprobe failed to detect container format (exit code {returncode})")

    format_name = json.loads(stdout.decode("utf-8"))["format"]["format_name"]

    # ffprobe returns comma-separated candidates (e.g. "mov,mp4,m4a,3gp,...");
    # pick the first as the canonical container name.
    return format_name.split(",")[0].lower()

def get_extension_for_muxer(muxer: str) -> str:
    """Convert an ffmpeg muxer name to a filename extension ffmpeg autodetects."""
    return _MUXER_EXTENSION_MAP.get(muxer, muxer)
