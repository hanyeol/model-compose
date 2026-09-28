from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from ..files import get_file_extension
from ..shell import run_command
from .executable import resolve_ffprobe_executable
import json

# Requested field name → (section, ffprobe key). section is "format" or "stream".
_VIDEO_FIELDS: Dict[str, Tuple[str, str]] = {
    "format":     ("format", "format_name"),
    "duration":   ("format", "duration"),
    "start_time": ("format", "start_time"),
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

def _parse_field_value(field: str, value: Any, hint: Optional[str] = None) -> Any:
    if value is None:
        return None

    if field == "format":
        # ffprobe names a demuxer group, not one container: mp4 reports
        # "mov,mp4,m4a,3gp,3g2,mj2", and .mkv and .webm both report
        # "matroska,webm". Prefer the extension the file was addressed by.
        candidates = [ candidate.strip().lower() for candidate in value.split(",") if candidate.strip() ]

        if hint and hint in candidates:
            return hint

        return candidates[0] if candidates else None

    if field == "frame_rate":
        numerator, denominator = value.split("/")
        return float(numerator) / float(denominator)

    if field in ("duration", "start_time"):
        return float(value)

    if field in ("size", "bit_rate", "sample_rate", "channels", "width", "height"):
        return int(value)

    return value

async def _probe(
    path: str,
    fields: Sequence[str],
    stream_selector: str,
    field_map: Dict[str, Tuple[str, str]],
) -> Tuple[Any, ...]:
    for field in fields:
        if field not in field_map:
            raise ValueError(f"Unknown ffprobe field: {field}")

    sections = { field_map[field][0] for field in fields }

    command = [ resolve_ffprobe_executable(), "-v", "quiet", "-print_format", "json" ]

    if "stream" in sections:
        command.extend([ "-select_streams", stream_selector, "-show_streams" ])

    if "format" in sections:
        command.append("-show_format")

    command.append(path)

    stdout, _, returncode = await run_command(command)

    if returncode != 0:
        raise RuntimeError(f"ffprobe failed to read metadata (exit code {returncode})")

    result = json.loads(stdout.decode("utf-8"))
    format = result.get("format") or {}
    streams = result.get("streams") or []
    stream = streams[0] if streams else {}

    hint = get_file_extension(path)

    values = []
    for field in fields:
        section, key = field_map[field]
        source = format if section == "format" else stream
        values.append(_parse_field_value(field, source.get(key), hint))

    return tuple(values)

async def probe_video(path: str, fields: Sequence[str]) -> Tuple[Any, ...]:
    """Probe a video file with a single ffprobe call and return the requested fields in order.

    Supported fields: 'format', 'duration', 'start_time', 'size', 'bit_rate' (from container),
    'codec', 'width', 'height', 'frame_rate', 'pix_fmt' (from the first video stream).
    """
    return await _probe(path, fields, "v:0", _VIDEO_FIELDS)

async def probe_audio(path: str, fields: Sequence[str]) -> Tuple[Any, ...]:
    """Probe an audio file with a single ffprobe call and return the requested fields in order.

    Supported fields: 'format', 'duration', 'size', 'bit_rate' (from container),
    'codec', 'sample_rate', 'channels', 'channel_layout' (from the first audio stream).
    """
    return await _probe(path, fields, "a:0", _AUDIO_FIELDS)

async def probe_video_keyframes(path: str, interval: Optional[Tuple[Optional[float], float]] = None) -> List[Tuple[float, int]]:
    """List `(pts, packet_index)` for every video keyframe in the scanned range.

    `interval` optionally scopes the scan to `(start, end)` absolute seconds — pass
    `start=None` for an open start (needed when a keyframe sits exactly on the
    window boundary in some containers). Reading a bounded interval is much
    cheaper than a full scan on large files, but the interval must cover a full
    GOP or the result may be empty; callers escalate to a wider window (or a
    full scan) when needed.

    `packet_index` is the keyframe's 0-based position in the packet stream this
    scan iterated (counting every video packet, not just keyframes). Indices
    are only meaningful within one call — subtracting indices from different
    scans yields garbage, so callers computing packet counts between two
    keyframes must source both from the same call.
    """
    command = [
        resolve_ffprobe_executable(), "-v", "quiet", "-print_format", "json",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
    ]

    if interval is not None:
        start, end = interval
        # `-read_intervals` uses absolute pts (i.e. includes format.start_time).
        # `%end` form makes the interval open on the start side so a keyframe
        # exactly on the boundary isn't missed (mpegts).
        command.extend([ "-read_intervals", f"{start:.6f}%{end:.6f}" if start is not None else f"%{end:.6f}" ])

    command.append(path)

    stdout, _, returncode = await run_command(command)

    if returncode != 0:
        raise RuntimeError(f"ffprobe failed to read keyframes (exit code {returncode})")

    payload = json.loads(stdout.decode("utf-8"))
    packets = payload.get("packets") or []
    keyframes: List[Tuple[float, int]] = []

    for index, packet in enumerate(packets):
        if "K" not in (packet.get("flags") or ""):
            continue

        pts = packet.get("pts_time")

        if pts is None:
            continue

        keyframes.append((float(pts), index))

    return keyframes
