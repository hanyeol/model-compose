from __future__ import annotations

from typing import Optional, List, Dict, Any
from mindor.dsl.schema.component import VideoAnalyzerComponentConfig, VideoAnalyzerDriver
from mindor.dsl.schema.action import VideoAnalyzerActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.ffmpeg import values as ffmpeg_values
from mindor.core.utils.shell import run_subprocess
from ....action.media import MediaInputPathResolver
from ..base import VideoAnalyzerService, register_video_analyzer_service
from ..base import ComponentActionContext
from .common import VideoAnalyzerAction
import re

class FFmpegVideoAnalyzerAction(VideoAnalyzerAction):
    async def _analyze_black(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Dict[str, Any]:
        # blackdetect emits `black_start`/`black_end`/`black_duration` on stderr.
        video_filter = (
            f"blackdetect=d={params['min_duration']}"
            f":pix_th={params['pixel_threshold']}"
            f":pic_th={params['picture_threshold']}"
        )
        stderr_text = await self._run_ffmpeg_filter(source, video_filter)

        regions = self._parse_blackdetect(stderr_text)
        total_black = sum((region.get("duration") or 0.0) for region in regions)
        duration = self._parse_duration(stderr_text)
        black_ratio = (total_black / duration) if duration else 0.0

        return {
            "min_duration":       params["min_duration"],
            "pixel_threshold":    params["pixel_threshold"],
            "picture_threshold":  params["picture_threshold"],
            "duration":           duration,
            "total_black":        total_black,
            "black_ratio":        black_ratio,
            "regions":            regions,
        }

    async def _analyze_freeze(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Dict[str, Any]:
        # freezedetect emits `freeze_start`/`freeze_end`/`freeze_duration`. The
        # `n` parameter is a normalized noise threshold (0.0-1.0); ffmpeg also
        # accepts dB values with a `dB` suffix but we standardize on the ratio.
        video_filter = (
            f"freezedetect=n={params['noise_threshold']}"
            f":d={params['min_duration']}"
        )
        stderr_text = await self._run_ffmpeg_filter(source, video_filter)

        regions = self._parse_freezedetect(stderr_text)
        total_freeze = sum((region.get("duration") or 0.0) for region in regions)
        duration = self._parse_duration(stderr_text)
        freeze_ratio = (total_freeze / duration) if duration else 0.0

        return {
            "min_duration":    params["min_duration"],
            "noise_threshold": params["noise_threshold"],
            "duration":        duration,
            "total_freeze":    total_freeze,
            "freeze_ratio":    freeze_ratio,
            "regions":         regions,
        }

    async def _analyze_brightness(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Dict[str, Any]:
        # signalstats.YAVG is the mean luma per frame (0-255 for 8-bit).
        # metadata=print pushes it to stderr; fps=... limits how many frames
        # we sample so long videos don't burn CPU.
        sample_rate = params["sample_rate"]
        video_filter = (
            f"fps={sample_rate},signalstats,"
            "metadata=print:key=lavfi.signalstats.YAVG:direct=1"
        )
        stderr_text = await self._run_ffmpeg_filter(source, video_filter)

        samples = self._parse_metadata_samples(stderr_text, "lavfi.signalstats.YAVG")
        values = [ sample["value"] for sample in samples ]

        stats = self._summarize(values)
        duration = self._parse_duration(stderr_text)

        result: Dict[str, Any] = {
            "sample_rate":     sample_rate,
            "sample_count":    len(values),
            "duration":        duration,
            "mean_brightness": stats["mean"],
            "min_brightness":  stats["min"],
            "max_brightness":  stats["max"],
            "std_brightness":  stats["std"],
        }

        if params["include_timeline"]:
            result["timeline"] = samples

        return result

    async def _analyze_motion(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Dict[str, Any]:
        # scdet reports a scene-change score per frame; higher = more different
        # from the previous frame. It's a coarse but cheap motion proxy that
        # doesn't need actual motion vectors. `t=0` disables the built-in
        # threshold gate so we get every frame's score.
        sample_rate = params["sample_rate"]
        video_filter = (
            f"fps={sample_rate},scdet=t=0,"
            "metadata=print:key=lavfi.scd.score:direct=1"
        )
        stderr_text = await self._run_ffmpeg_filter(source, video_filter)

        samples = self._parse_metadata_samples(stderr_text, "lavfi.scd.score")
        values = [ sample["value"] for sample in samples ]

        stats = self._summarize(values)
        duration = self._parse_duration(stderr_text)

        result: Dict[str, Any] = {
            "sample_rate":  sample_rate,
            "sample_count": len(values),
            "duration":     duration,
            "mean_motion":  stats["mean"],
            "min_motion":   stats["min"],
            "max_motion":   stats["max"],
            "std_motion":   stats["std"],
        }

        if params["include_timeline"]:
            result["timeline"] = samples

        return result

    async def _run_ffmpeg_filter(
        self,
        source: MediaSource,
        video_filter: str,
        cancellation_token: Optional[CancellationToken]
    ) -> str:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "video" ])

        command = [ "ffmpeg", "-hide_banner", "-nostats" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        command.extend([ "-an", "-vf", video_filter, "-f", "null", "-" ])

        try:
            process, _, stderr = await run_subprocess(
                command,
                source.stream if input_path is None else None,
                stdout_handler=lambda r: r.read(),
                stderr_handler=lambda r: r.read(),
            )
            if process.returncode != 0:
                error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
                raise RuntimeError(f"ffmpeg filter '{video_filter}' failed (exit code {process.returncode}): {error_message}")
        finally:
            if spooled and input_path is not None:
                self._remove_file(input_path)

        return stderr.decode("utf-8", errors="replace") if stderr else ""

    @staticmethod
    def _parse_blackdetect(text: str) -> List[Dict[str, float]]:
        # Lines look like:
        #   [blackdetect @ 0x...] black_start:12.3 black_end:15.6 black_duration:3.3
        pattern = re.compile(
            r"black_start:\s*(?P<start>-?\d+(?:\.\d+)?)\s+"
            r"black_end:\s*(?P<end>-?\d+(?:\.\d+)?)\s+"
            r"black_duration:\s*(?P<duration>-?\d+(?:\.\d+)?)"
        )

        return [
            {
                "start_time": float(m.group("start")),
                "end_time":   float(m.group("end")),
                "duration":   float(m.group("duration")),
            }
            for m in pattern.finditer(text)
        ]

    @staticmethod
    def _parse_freezedetect(text: str) -> List[Dict[str, float]]:
        # freezedetect prints `freeze_start`, `freeze_duration`, `freeze_end`
        # (in that order) on separate lines per region. A freeze that runs to
        # EOF has a start without matching end/duration lines.
        starts = [ float(m.group(1)) for m in re.finditer(r"freeze_start:\s*(-?\d+(?:\.\d+)?)", text) ]
        end_pairs = [
            (float(duration), float(end))
            for duration, end in re.findall(
                r"freeze_duration:\s*(-?\d+(?:\.\d+)?)[^\n]*?freeze_end:\s*(-?\d+(?:\.\d+)?)",
                text,
                flags=re.DOTALL,
            )
        ]

        regions: List[Dict[str, float]] = []

        for index, start in enumerate(starts):
            if index < len(end_pairs):
                duration, end = end_pairs[index]
                regions.append({ "start_time": start, "end_time": end, "duration": duration })
            else:
                regions.append({ "start_time": start, "end_time": None, "duration": None })

        return regions

    @staticmethod
    def _parse_metadata_samples(text: str, key: str) -> List[Dict[str, float]]:
        # `metadata=print` produces pairs of lines:
        #   [Parsed_metadata_N @ 0x...] frame:12   pts:12000 pts_time:0.5
        #   [Parsed_metadata_N @ 0x...] lavfi.signalstats.YAVG=42.500
        # We pair each timing line with the following value line for `key`.
        timing_pattern = re.compile(r"frame:\s*(\d+)\s+pts:\s*\d+\s+pts_time:\s*(-?\d+(?:\.\d+)?)")
        value_pattern = re.compile(rf"{re.escape(key)}=(-?\d+(?:\.\d+)?|nan|inf|-inf)")

        samples: List[Dict[str, float]] = []
        cursor = 0

        while True:
            timing_match = timing_pattern.search(text, cursor)

            if not timing_match:
                break

            value_match = value_pattern.search(text, timing_match.end())

            if not value_match:
                break

            value = ffmpeg_values.parse_float(value_match.group(1))

            if value is not None:
                samples.append({
                    "frame": int(timing_match.group(1)),
                    "time":  float(timing_match.group(2)),
                    "value": value,
                })
            cursor = value_match.end()

        return samples

    @staticmethod
    def _summarize(values: List[float]) -> Dict[str, Optional[float]]:
        if not values:
            return { "mean": None, "min": None, "max": None, "std": None }
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return {
            "mean": mean,
            "min":  min(values),
            "max":  max(values),
            "std":  variance ** 0.5,
        }

    @staticmethod
    def _parse_duration(text: str) -> Optional[float]:
        # ffmpeg prints `Duration: HH:MM:SS.ms` in its stderr header. This is
        # the source's declared duration, not the amount actually decoded.
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)

        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

        return None

@register_video_analyzer_service(VideoAnalyzerDriver.FFMPEG)
class FFmpegVideoAnalyzerService(VideoAnalyzerService):
    def __init__(self, id: str, config: VideoAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(
        self,
        action: VideoAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await FFmpegVideoAnalyzerAction(action).run(context)
