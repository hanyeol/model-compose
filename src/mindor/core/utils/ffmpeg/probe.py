from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple
from ..shell import run_command
import json

# Requested field name → (section, ffprobe key). section is "format" or "stream".
_VIDEO_FIELDS: Dict[str, Tuple[str, str]] = {
    "format":     ("format", "format_name"),
    "duration":   ("format", "duration"),
    "size":       ("format", "size"),
    "bit_rate":   ("format", "bit_rate"),
    "codec":      ("stream", "codec_name"),
    "width":      ("stream", "width"),
    "height":     ("stream", "height"),
    "frame_rate": ("stream", "r_frame_rate"),
    "pix_fmt":    ("stream", "pix_fmt"),
}

_AUDIO_FIELDS: Dict[str, Tuple[str, str]] = {
    "format":         ("format", "format_name"),
    "duration":       ("format", "duration"),
    "size":           ("format", "size"),
    "bit_rate":       ("format", "bit_rate"),
    "codec":          ("stream", "codec_name"),
    "sample_rate":    ("stream", "sample_rate"),
    "channels":       ("stream", "channels"),
    "channel_layout": ("stream", "channel_layout"),
}

def _parse_field_value(field: str, value: Any) -> Any:
    if value is None:
        return None

    if field == "format":
        # ffprobe returns comma-separated candidates (e.g. "mov,mp4,m4a,3gp,...");
        # pick the first as the canonical container name.
        return value.split(",")[0].lower()

    if field == "frame_rate":
        numerator, denominator = value.split("/")
        return float(numerator) / float(denominator)

    if field in ("duration",):
        return float(value)

    if field in ("size", "bit_rate", "sample_rate", "channels", "width", "height"):
        return int(value)

    return value

async def _probe(
    input_path: str,
    fields: Sequence[str],
    stream_selector: str,
    field_map: Dict[str, Tuple[str, str]],
) -> Tuple[Any, ...]:
    for field in fields:
        if field not in field_map:
            raise ValueError(f"Unknown ffprobe field: {field}")

    sections = { field_map[field][0] for field in fields }

    command = [ "ffprobe", "-v", "quiet", "-print_format", "json" ]

    if "stream" in sections:
        command.extend([ "-select_streams", stream_selector, "-show_streams" ])
    if "format" in sections:
        command.append("-show_format")

    command.append(input_path)

    stdout, _, returncode = await run_command(command)

    if returncode != 0:
        raise RuntimeError(f"ffprobe failed to read metadata (exit code {returncode})")

    result = json.loads(stdout.decode("utf-8"))
    format = result.get("format") or {}
    streams = result.get("streams") or []
    stream = streams[0] if streams else {}

    values = []
    for field in fields:
        section, key = field_map[field]
        source = format if section == "format" else stream
        values.append(_parse_field_value(field, source.get(key)))

    return tuple(values)

async def probe_video(input_path: str, fields: Sequence[str]) -> Tuple[Any, ...]:
    """Probe a video file with a single ffprobe call and return the requested fields in order.

    Supported fields: 'format', 'duration', 'size', 'bit_rate' (from container),
    'codec', 'width', 'height', 'frame_rate', 'pix_fmt' (from the first video stream).
    """
    return await _probe(input_path, fields, "v:0", _VIDEO_FIELDS)

async def probe_audio(input_path: str, fields: Sequence[str]) -> Tuple[Any, ...]:
    """Probe an audio file with a single ffprobe call and return the requested fields in order.

    Supported fields: 'format', 'duration', 'size', 'bit_rate' (from container),
    'codec', 'sample_rate', 'channels', 'channel_layout' (from the first audio stream).
    """
    return await _probe(input_path, fields, "a:0", _AUDIO_FIELDS)
