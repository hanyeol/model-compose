from __future__ import annotations

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import AudioSegmentDetectorComponentConfig, AudioSegmentDetectorDriver
from mindor.dsl.schema.action import AudioSegmentDetectorActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.shell import run_subprocess
from ....action.media import MediaInputPathResolver
from ..base import AudioSegmentDetectorService, register_audio_segment_detector_service
from ..base import ComponentActionContext
from .common import AudioSegmentDetectorAction
import asyncio, os, re

class FFmpegAudioSegmentDetectorAction(AudioSegmentDetectorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        silence_threshold = await context.render_scalar(self.config.silence_threshold, float)

        params.update({
            "silence_threshold": silence_threshold,
        })

        return params

    async def _detect_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._detect(audio, params, cancellation_token) for audio in audios
        ])

    async def _detect(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        threshold    = params["silence_threshold"]
        min_duration = params["min_segment_duration"] or 0.0

        # silencedetect emits `silence_start` / `silence_end` events on stderr.
        # `d=` is the minimum silent-run length that qualifies as a boundary;
        # feeding min_segment_duration keeps short pauses inside a segment.
        audio_filter = f"silencedetect=noise={threshold}dB:d={min_duration}"
        stderr_text = await self._run_ffmpeg_filter(source, audio_filter)

        silences = self._parse_silencedetect(stderr_text)
        duration = self._parse_duration(stderr_text) or 0.0

        segments = self._silences_to_segments(silences, duration, params["return_labels"])
        segments = self._merge_short_segments(segments, params["min_segment_duration"])

        return {
            "segments": segments,
            "duration": duration,
            "sample_rate": params["sample_rate"],
        }

    async def _run_ffmpeg_filter(self, source: MediaSource, audio_filter: str) -> str:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        command = [ "ffmpeg", "-hide_banner", "-nostats" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        command.extend([ "-af", audio_filter, "-f", "null", "-" ])

        try:
            process, _, stderr = await run_subprocess(
                command,
                source.stream if input_path is None else None,
                stdout_handler=lambda r: r.read(),
                stderr_handler=lambda r: r.read(),
            )
            if process.returncode != 0:
                error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
                raise RuntimeError(f"ffmpeg filter '{audio_filter}' failed (exit code {process.returncode}): {error_message}")
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        return stderr.decode("utf-8", errors="replace") if stderr else ""

    @staticmethod
    def _silences_to_segments(
        silences: List[Dict[str, Optional[float]]],
        duration: float,
        return_labels: bool,
    ) -> List[Dict[str, Any]]:
        # Convert silence regions into non-silent segments (the gaps between
        # silences). Silences themselves are dropped — callers wanting them
        # can invert this list.
        segments: List[Dict[str, Any]] = []
        cursor = 0.0

        for silence in silences:
            start = silence.get("start") or 0.0
            end = silence.get("end")

            if start > cursor:
                segment: Dict[str, Any] = { "start_time": float(cursor), "end_time": float(start) }
                if return_labels:
                    segment["label"] = "voice"
                segments.append(segment)

            # If `end` is missing, the silence runs to EOF and there is no more
            # audible content to emit.
            if end is None:
                cursor = duration
                break

            cursor = end

        if cursor < duration:
            segment = { "start_time": float(cursor), "end_time": float(duration) }
            if return_labels:
                segment["label"] = "voice"
            segments.append(segment)

        return segments

    @staticmethod
    def _parse_silencedetect(text: str) -> List[Dict[str, Optional[float]]]:
        # silencedetect emits paired lines per region:
        #   [silencedetect @ 0x...] silence_start: 12.345
        #   [silencedetect @ 0x...] silence_end: 15.678 | silence_duration: 3.333
        starts = [ float(m.group(1)) for m in re.finditer(r"silence_start:\s*(-?\d+(?:\.\d+)?)", text) ]
        ends   = re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(-?\d+(?:\.\d+)?)", text)
        regions: List[Dict[str, Optional[float]]] = []

        for index, start in enumerate(starts):
            if index < len(ends):
                end, duration = ends[index]
                regions.append({ "start": start, "end": float(end), "duration": float(duration) })
            else:
                # Silence that runs to EOF gets a start without an end.
                regions.append({ "start": start, "end": None, "duration": None })

        return regions

    @staticmethod
    def _parse_duration(text: str) -> Optional[float]:
        # ffmpeg prints `Duration: HH:MM:SS.ms` in its stderr header.
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)

        if not m:
            return None

        hours, minutes, seconds = m.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

@register_audio_segment_detector_service(AudioSegmentDetectorDriver.FFMPEG)
class FFmpegAudioSegmentDetectorService(AudioSegmentDetectorService):
    def __init__(self, id: str, config: AudioSegmentDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(
        self,
        action: AudioSegmentDetectorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await FFmpegAudioSegmentDetectorAction(action).run(context)
