from __future__ import annotations

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import AudioSilenceDetectorComponentConfig, AudioSilenceDetectorDriver
from mindor.dsl.schema.action import AudioSilenceDetectorActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.ffmpeg import values as ffmpeg_values
from mindor.core.utils.shell import run_subprocess
from ....action.media import MediaInputPathResolver
from ..base import AudioSilenceDetectorService, register_audio_silence_detector_service
from ..base import ComponentActionContext
from .common import AudioSilenceDetectorAction
import asyncio, os, re

class FFmpegAudioSilenceDetectorAction(AudioSilenceDetectorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        silence_threshold    = await context.render_scalar(self.config.silence_threshold, float)
        min_silence_duration = await context.render_scalar(self.config.min_silence_duration, "time")

        return {
            "silence_threshold":    silence_threshold,
            "min_silence_duration": min_silence_duration,
        }

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
        min_duration = params["min_silence_duration"] or 0.0

        audio_filter = f"silencedetect=noise={threshold}dB:d={min_duration}"
        stderr_text = await self._run_ffmpeg_filter(source, audio_filter)

        silences = self._parse_silencedetect(stderr_text)
        duration = ffmpeg_values.read_duration(stderr_text, "Duration") or 0.0
        segments = self._build_segments(silences, duration)

        return {
            "segments": segments,
            "duration": duration,
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
    def _build_segments(
        silences: List[Dict[str, Optional[float]]],
        duration: float,
    ) -> List[Dict[str, Any]]:
        # Interleave `audible` runs with `silence` runs so callers get a single
        # ordered timeline spanning the whole audio.
        segments: List[Dict[str, Any]] = []
        cursor = 0.0

        for silence in silences:
            start = silence.get("start") or 0.0
            end   = silence.get("end")

            if start > cursor:
                segments.append({ "start_time": float(cursor), "end_time": float(start), "type": "audible" })

            if end is None:
                # Silence runs to EOF: emit it up to `duration` and stop.
                if duration > start:
                    segments.append({ "start_time": float(start), "end_time": float(duration), "type": "silence" })
                cursor = duration
                break

            segments.append({ "start_time": float(start), "end_time": float(end), "type": "silence" })
            cursor = end

        if cursor < duration:
            segments.append({ "start_time": float(cursor), "end_time": float(duration), "type": "audible" })

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

@register_audio_silence_detector_service(AudioSilenceDetectorDriver.FFMPEG)
class FFmpegAudioSilenceDetectorService(AudioSilenceDetectorService):
    def __init__(self, id: str, config: AudioSilenceDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(
        self,
        action: AudioSilenceDetectorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await FFmpegAudioSilenceDetectorAction(action).run(context)
