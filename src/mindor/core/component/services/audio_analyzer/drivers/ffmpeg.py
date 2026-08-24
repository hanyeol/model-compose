from __future__ import annotations

from typing import Optional, List, Dict, Any
from mindor.dsl.schema.component import AudioAnalyzerComponentConfig, AudioAnalyzerDriver
from mindor.dsl.schema.action import AudioAnalyzerActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.ffmpeg import values as ffmpeg_values
from mindor.core.utils.shell import run_subprocess
from ....action.media import MediaInputPathResolver
from ..base import AudioAnalyzerService, register_audio_analyzer_service
from ..base import ComponentActionContext
from .common import AudioAnalyzerAction
import os, re

class FFmpegAudioAnalyzerAction(AudioAnalyzerAction):
    async def _analyze_loudness(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        # ebur128 emits an EBU R128 summary block on stderr; enabling `peak=true`
        # also yields sample and true-peak numbers per pass.
        target           = params["target_loudness"]
        include_timeline = params["include_timeline"]

        audio_filter = f"ebur128=peak=true:target={int(target)}"
        stderr_text = await self._run_ffmpeg_filter(source, audio_filter)

        summary = self._parse_ebur128_summary(stderr_text)

        result: Dict[str, Any] = {
            "integrated_loudness": summary.get("integrated"),
            "loudness_range":      summary.get("range"),
            "loudness_range_low":  summary.get("range_low"),
            "loudness_range_high": summary.get("range_high"),
            "threshold_integrated": summary.get("threshold_integrated"),
            "threshold_range":      summary.get("threshold_range"),
            "sample_peak_dbfs":    summary.get("sample_peak"),
            "true_peak_dbtp":      summary.get("true_peak"),
            "target_loudness":     target,
        }

        if include_timeline:
            result["timeline"] = self._parse_ebur128_timeline(stderr_text)

        return result

    async def _analyze_peak(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        # astats produces per-channel and overall peak/RMS stats on stderr.
        # ebur128 (with peak=true) is the standard source for true-peak (dBTP).
        stderr_text = await self._run_ffmpeg_filter(source, "astats=metadata=0:reset=0")
        stats = self._parse_astats(stderr_text)

        result: Dict[str, Any] = {
            "sample_peak_dbfs":     stats.get("peak_level"),
            "max_sample":           stats.get("max_level"),
            "min_sample":           stats.get("min_level"),
        }

        if params["true_peak"]:
            stderr_text = await self._run_ffmpeg_filter(source, "ebur128=peak=true")
            summary = self._parse_ebur128_summary(stderr_text)
            result["true_peak_dbtp"] = summary.get("true_peak")

        return result

    async def _analyze_gain(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        stderr_text = await self._run_ffmpeg_filter(source, "astats=metadata=0:reset=0")
        stats = self._parse_astats(stderr_text)

        peak = stats.get("peak_level")
        headroom = -peak if peak is not None else None

        return {
            "rms_dbfs":        stats.get("rms_level"),
            "rms_peak_dbfs":   stats.get("rms_peak"),
            "rms_trough_dbfs": stats.get("rms_trough"),
            "peak_dbfs":       peak,
            "headroom_db":     headroom,
            "dc_offset":       stats.get("dc_offset"),
            "crest_factor":    stats.get("crest_factor"),
            "flat_factor":     stats.get("flat_factor"),
        }

    async def _analyze_clipping(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        # astats reports the number of samples at or above digital full-scale.
        # For threshold-based detection at anything other than 0 dBFS we still
        # need to walk the PCM, so we surface astats' clipping counts and
        # leave finer analysis to callers that supply their own threshold.
        stderr_text = await self._run_ffmpeg_filter(source, "astats=metadata=0:reset=0")
        stats = self._parse_astats(stderr_text)

        number_of_samples = stats.get("number_of_samples") or 0
        clipped = stats.get("number_of_clippings") or 0
        clipped_ratio = (clipped / number_of_samples) if number_of_samples else 0.0

        return {
            "threshold_dbfs":         params["threshold"],
            "min_consecutive_length": params["min_consecutive_length"],
            "sample_count":           number_of_samples,
            "clipped_sample_count":   clipped,
            "clipped_ratio":          clipped_ratio,
            "peak_dbfs":              stats.get("peak_level"),
            "regions":                [],
        }

    async def _analyze_silence(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        threshold    = params["threshold"]
        min_duration = params["min_duration"]

        audio_filter = f"silencedetect=noise={threshold}dB:d={min_duration}"
        stderr_text = await self._run_ffmpeg_filter(source, audio_filter)

        regions = self._parse_silencedetect(stderr_text)
        total_silent = sum((region.get("duration") or 0.0) for region in regions)

        # Overall duration falls out of astats' `samples` and rate — but the
        # cheaper answer is to grab it from ffmpeg's own progress line if we
        # can, else leave silent_ratio null when we don't know the duration.
        duration = self._parse_duration(stderr_text)
        silent_ratio = (total_silent / duration) if duration else 0.0

        return {
            "threshold_dbfs":     threshold,
            "min_duration":       min_duration,
            "duration":           duration,
            "total_silent":       total_silent,
            "silent_ratio":       silent_ratio,
            "regions":            regions,
        }

    async def _run_ffmpeg_filter(
        self,
        source: MediaSource,
        audio_filter: str,
        cancellation_token: Optional[CancellationToken]
    ) -> str:
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
    def _parse_ebur128_summary(text: str) -> Dict[str, Optional[float]]:
        # ebur128 prints the summary after `Summary:\n\n`, one metric per line.
        # Example lines:
        #   Integrated loudness:
        #     I:         -23.0 LUFS
        #     Threshold: -33.7 LUFS
        #   Loudness range:
        #     LRA:         5.2 LU
        #     Threshold: -43.7 LUFS
        #     LRA low:  -25.6 LUFS
        #     LRA high: -20.4 LUFS
        #   Sample peak:
        #     Peak:      -1.2 dBFS
        #   True peak:
        #     Peak:      -0.8 dBTP
        summary_text = text.rsplit("Summary:", 1)[-1] if "Summary:" in text else ""

        def _match(pattern: str) -> Optional[float]:
            m = re.search(pattern, summary_text)
            return float(m.group(1)) if m else None

        # `Peak:` appears in both sample-peak and true-peak blocks; pull them
        # from their sections rather than globally.
        sample_peak = None
        true_peak   = None

        if "Sample peak:" in summary_text:
            sp_section = summary_text.split("Sample peak:", 1)[1]
            m = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", sp_section)
            sample_peak = float(m.group(1)) if m else None

        if "True peak:" in summary_text:
            tp_section = summary_text.split("True peak:", 1)[1]
            m = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBTP", tp_section)
            true_peak = float(m.group(1)) if m else None

        # Integrated / range live in the Integrated / Loudness range blocks.
        integrated           = None
        threshold_integrated = None

        if "Integrated loudness:" in summary_text:
            block = summary_text.split("Integrated loudness:", 1)[1].split("Loudness range:", 1)[0]
            m = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", block)
            integrated = float(m.group(1)) if m else None
            m = re.search(r"Threshold:\s*(-?\d+(?:\.\d+)?)\s*LUFS", block)
            threshold_integrated = float(m.group(1)) if m else None

        range_value     = None
        threshold_range = None
        range_low       = None
        range_high      = None

        if "Loudness range:" in summary_text:
            block = summary_text.split("Loudness range:", 1)[1]
            m = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", block)
            range_value = float(m.group(1)) if m else None
            m = re.search(r"Threshold:\s*(-?\d+(?:\.\d+)?)\s*LUFS", block)
            threshold_range = float(m.group(1)) if m else None
            m = re.search(r"LRA low:\s*(-?\d+(?:\.\d+)?)\s*LUFS", block)
            range_low = float(m.group(1)) if m else None
            m = re.search(r"LRA high:\s*(-?\d+(?:\.\d+)?)\s*LUFS", block)
            range_high = float(m.group(1)) if m else None

        return {
            "integrated":           integrated,
            "threshold_integrated": threshold_integrated,
            "range":                range_value,
            "threshold_range":      threshold_range,
            "range_low":            range_low,
            "range_high":           range_high,
            "sample_peak":          sample_peak,
            "true_peak":            true_peak,
        }

    @staticmethod
    def _parse_ebur128_timeline(text: str) -> List[Dict[str, float]]:
        # Per-window lines look like:
        #   [Parsed_ebur128_0 @ 0x...] t: 0.4     M:-70.0  S:-70.0  I:-70.0 LUFS  ...
        pattern = re.compile(
            r"t:\s*(?P<t>-?\d+(?:\.\d+)?)\s+"
            r"M:\s*(?P<m>-?\d+(?:\.\d+)?|inf|-inf)\s+"
            r"S:\s*(?P<s>-?\d+(?:\.\d+)?|inf|-inf)\s+"
            r"I:\s*(?P<i>-?\d+(?:\.\d+)?|inf|-inf)"
        )
        entries: List[Dict[str, float]] = []
        for m in pattern.finditer(text):
            entries.append({
                "time":       float(m.group("t")),
                "momentary":  ffmpeg_values.parse_float(m.group("m")),
                "short_term": ffmpeg_values.parse_float(m.group("s")),
                "integrated": ffmpeg_values.parse_float(m.group("i")),
            })
        return entries

    @staticmethod
    def _parse_astats(text: str) -> Dict[str, Optional[float]]:
        # astats prints an `Overall` block after per-channel blocks; we take
        # values from Overall so the numbers span the whole track.
        overall_text = text.rsplit("Overall", 1)[-1] if "Overall" in text else text

        def _match_float(label: str) -> Optional[float]:
            m = re.search(rf"{re.escape(label)}:\s*(-?\d+(?:\.\d+)?|inf|-inf|nan)", overall_text)
            return ffmpeg_values.parse_float(m.group(1)) if m else None

        def _match_int(label: str) -> Optional[int]:
            m = re.search(rf"{re.escape(label)}:\s*(\d+)", overall_text)
            return int(m.group(1)) if m else None

        return {
            "dc_offset":            _match_float("DC offset"),
            "min_level":            _match_float("Min level"),
            "max_level":            _match_float("Max level"),
            "peak_level":           _match_float("Peak level dB"),
            "rms_level":            _match_float("RMS level dB"),
            "rms_peak":             _match_float("RMS peak dB"),
            "rms_trough":           _match_float("RMS trough dB"),
            "crest_factor":         _match_float("Crest factor"),
            "flat_factor":          _match_float("Flat factor"),
            "number_of_samples":    _match_int("Number of samples"),
            "number_of_clippings":  _match_int("Number of clippings"),
        }

    @staticmethod
    def _parse_silencedetect(text: str) -> List[Dict[str, float]]:
        # silencedetect emits paired lines per region:
        #   [silencedetect @ 0x...] silence_start: 12.345
        #   [silencedetect @ 0x...] silence_end: 15.678 | silence_duration: 3.333
        starts = [ float(m.group(1)) for m in re.finditer(r"silence_start:\s*(-?\d+(?:\.\d+)?)", text) ]
        ends   = re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(-?\d+(?:\.\d+)?)", text)
        regions: List[Dict[str, float]] = []

        for index, start in enumerate(starts):
            if index < len(ends):
                end, duration = ends[index]
                regions.append({ "start": start, "end": float(end), "duration": float(duration) })
            else:
                # Silence that runs to EOF gets a start without an end; report
                # what we know and leave `end`/`duration` unset.
                regions.append({ "start": start, "end": None, "duration": None })

        return regions

    @staticmethod
    def _parse_duration(text: str) -> Optional[float]:
        # ffmpeg prints `Duration: HH:MM:SS.ms` in its stderr header. This is
        # the source's declared duration, not the amount actually decoded.
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)

        if not m:
            return None

        hours, minutes, seconds = m.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

@register_audio_analyzer_service(AudioAnalyzerDriver.FFMPEG)
class FFmpegAudioAnalyzerService(AudioAnalyzerService):
    def __init__(self, id: str, config: AudioAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(
        self,
        action: AudioAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await FFmpegAudioAnalyzerAction(action).run(context)
