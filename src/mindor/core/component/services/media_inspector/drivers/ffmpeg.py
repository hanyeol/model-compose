from __future__ import annotations

from typing import Optional, Dict, List, Any
from fractions import Fraction
from mindor.dsl.schema.component import MediaInspectorComponentConfig, MediaInspectorDriver
from mindor.dsl.schema.action import MediaInspectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.shell import run_command, run_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import MediaInspectorService, register_media_inspector_service
from ..base import ComponentActionContext
from .common import MediaInspectorAction
import asyncio, json

class FFmpegMediaInspectorAction(MediaInspectorAction):
    async def _inspect_batch(
        self,
        sources: List[MediaSource],
        return_raw: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._inspect(source, return_raw) for source in sources
        ])

    async def _inspect(self, source: MediaSource, return_raw: bool) -> Dict[str, Any]:
        input_path, spooled = await MediaInputPathResolver.resolve(source, streamable_media=[ "video", "audio" ])

        try:
            raw = await self._probe(input_path, source)

            format_info  = raw.get("format", {}) or {}
            streams_info = raw.get("streams", []) or []

            duration   = format_info.get("duration")
            size       = format_info.get("size")
            bitrate    = format_info.get("bit_rate")
            start_time = format_info.get("start_time")

            result: Dict[str, Any] = {
                "path":             input_path,
                "format":           self._pick_container_format(format_info.get("format_name"), source.format),
                "format_long_name": format_info.get("format_long_name"),
                "duration":         float(duration)   if duration   not in (None, "N/A") else None,
                "size":             int(size)         if size       not in (None, "N/A") else None,
                "bitrate":          int(bitrate)      if bitrate    not in (None, "N/A") else None,
                "start_time":       float(start_time) if start_time not in (None, "N/A") else None,
                "tags":             format_info.get("tags") or {},
                "video_streams":    [ self._normalize_video_stream(stream) for stream in streams_info if stream.get("codec_type") == "video" ],
                "audio_streams":    [ self._normalize_audio_stream(stream) for stream in streams_info if stream.get("codec_type") == "audio" ],
                "subtitle_streams": [ self._normalize_subtitle_stream(stream) for stream in streams_info if stream.get("codec_type") == "subtitle" ],
            }

            if return_raw:
                result["raw"] = raw

            return result
        finally:
            if spooled and input_path is not None:
                self._remove_file(input_path)

    @staticmethod
    async def _probe(input_path: Optional[str], source: MediaSource) -> Dict[str, Any]:
        # ffprobe reads from `pipe:0` when the caller wants us to consume
        # stdin. Only streamable containers reach this path (see the base
        # class's _resolve_input_path); mp4/mov/mkv still get spooled to a
        # file so ffprobe can seek their moov/cues.
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams",
            input_path if input_path is not None else "pipe:0",
        ]

        if input_path is not None:
            stdout, stderr, returncode = await run_command(command)
        else:
            process, stdout, stderr = await run_subprocess(
                command,
                source=source.stream,
                stdout_handler=lambda r: r.read(),
                stderr_handler=lambda r: r.read(),
            )
            returncode = process.returncode

        if returncode != 0:
            error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
            raise RuntimeError(f"ffprobe failed (exit code {returncode}): {error_message}")

        logging.debug("ffprobe completed: %s", f"'{input_path}'" if input_path is not None else "pipe:0")

        return json.loads(stdout.decode("utf-8"))

    @staticmethod
    def _pick_container_format(format_name: Optional[str], hint: Optional[str]) -> Optional[str]:
        # ffprobe returns comma-separated candidates (e.g. "mov,mp4,m4a,3gp,3g2,mj2").
        # If the caller-supplied hint is one of them, prefer it so the returned
        # `format` matches how the file was addressed upstream.
        if not format_name:
            return hint if hint else None

        candidates = [ candidate.strip().lower() for candidate in format_name.split(",") if candidate.strip() ]

        if hint and hint in candidates:
            return hint

        return candidates[0] if candidates else None

    def _normalize_video_stream(self, stream: Dict[str, Any]) -> Dict[str, Any]:
        bitrate  = stream.get("bit_rate")
        duration = stream.get("duration")
        frames   = stream.get("nb_frames")
        rotation = self._resolve_rotation(stream)

        return {
            "index":           stream.get("index"),
            "codec":           stream.get("codec_name"),
            "codec_long_name": stream.get("codec_long_name"),
            "profile":         stream.get("profile"),
            "width":           stream.get("width"),
            "height":          stream.get("height"),
            "pixel_format":    stream.get("pix_fmt"),
            "fps":             self._rational_to_float(stream.get("avg_frame_rate")) or self._rational_to_float(stream.get("r_frame_rate")),
            "bitrate":         int(bitrate)    if bitrate  not in (None, "N/A") else None,
            "duration":        float(duration) if duration not in (None, "N/A") else None,
            "frames":          int(frames)     if frames   not in (None, "N/A") else None,
            "aspect_ratio":    stream.get("display_aspect_ratio"),
            "rotation":        int(rotation)   if rotation not in (None, "N/A") else None,
            "tags":            stream.get("tags") or {},
        }

    def _normalize_audio_stream(self, stream: Dict[str, Any]) -> Dict[str, Any]:
        sample_rate = stream.get("sample_rate")
        bitrate     = stream.get("bit_rate")
        duration    = stream.get("duration")

        return {
            "index":           stream.get("index"),
            "codec":           stream.get("codec_name"),
            "codec_long_name": stream.get("codec_long_name"),
            "profile":         stream.get("profile"),
            "sample_rate":     int(sample_rate) if sample_rate not in (None, "N/A") else None,
            "channels":        stream.get("channels"),
            "channel_layout":  stream.get("channel_layout"),
            "sample_format":   stream.get("sample_fmt"),
            "bitrate":         int(bitrate)     if bitrate     not in (None, "N/A") else None,
            "duration":        float(duration)  if duration    not in (None, "N/A") else None,
            "tags":            stream.get("tags") or {},
        }

    def _normalize_subtitle_stream(self, stream: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "index":    stream.get("index"),
            "codec":    stream.get("codec_name"),
            "language": (stream.get("tags") or {}).get("language"),
            "tags":     stream.get("tags") or {},
        }

    @staticmethod
    def _resolve_rotation(stream: Dict[str, Any]) -> Any:
        # Rotation lives in the tag block on some inputs and in the newer
        # side_data_list block on others; prefer side_data when present.
        for entry in stream.get("side_data_list") or []:
            if "rotation" in entry:
                return entry["rotation"]

        return (stream.get("tags") or {}).get("rotate")

    @staticmethod
    def _rational_to_float(value: Any) -> Optional[float]:
        # ffprobe reports '0/0' when the rate is unknown; treat that as None so
        # callers can distinguish 'no fps' from 'zero fps'.
        if value and value not in ("0/0", "N/A"):
            try:
                return float(Fraction(value))
            except (ValueError, ZeroDivisionError):
                return float(value) if value not in (None, "N/A") else None

        return None

@register_media_inspector_service(MediaInspectorDriver.FFMPEG)
class FFmpegMediaInspectorService(MediaInspectorService):
    def __init__(self, id: str, config: MediaInspectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: MediaInspectorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegMediaInspectorAction(action).run(context)
