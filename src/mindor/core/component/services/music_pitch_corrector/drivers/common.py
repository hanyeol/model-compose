from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicPitchCorrectorActionConfig
from mindor.dsl.schema.action.impl.music_pitch_corrector.impl.common import (
    MusicPitchCorrectorActionMethod,
    MusicPitchCorrectionMode,
    MusicPitchCorrectionScale,
    MusicPitchCorrectionOutOfRangeMode,
    PitchUnit,
)
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.audio import AudioBufferStreamIterator
from mindor.core.foundation.streaming.resources import read_stream_to_buffer
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.audio import AudioBuffer
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.soundfile.audio import load_pcm_samples
from ....action.media import MediaInputPathResolver
from ....action.base import ComponentAction
from ..base import ComponentActionContext
from .planner import MusicPitchCorrectionPlanner
import asyncio
import os

if TYPE_CHECKING:
    import numpy as np

# Chunk size for streamed output from apply/correct. WORLD is a batch vocoder
# (its analysis step needs the whole signal), so this is strictly "output
# streaming over an already-synthesized waveform."
_STREAM_CHUNK_SECONDS = 1.0

# Scale presets — the only place pitch-class interval sets live. The planner
# receives already-expanded ``List[int]`` offsets, so adding a new scale name
# only requires an entry here (and in the ``MusicPitchCorrectionScale`` enum).
_SCALE_PRESETS: Dict[MusicPitchCorrectionScale, List[int]] = {
    MusicPitchCorrectionScale.MAJOR:     [ 0, 2, 4, 5, 7, 9, 11 ],
    MusicPitchCorrectionScale.MINOR:     [ 0, 2, 3, 5, 7, 8, 10 ],
    MusicPitchCorrectionScale.CHROMATIC: [ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 ],
}

class MusicPitchCorrectionCurve(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<Curve notes={len(self.get('notes', []))} "
            f"frames={len(self.get('frames', {}).get('time', []))}>"
        )

class MusicPitchCorrectionReport(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<Report total={self.get('notes_total')} "
            f"corrected={self.get('notes_corrected')} "
            f"warnings={len(self.get('warnings', []))}>"
        )

class MusicPitchCorrectorAction(ComponentAction):
    """Base action class shared by all drivers. Mirrors the music-analyzer /
    audio-processor shape: ``run`` prepares the input and params, then dispatches
    through a single ``_process`` method whose plan/apply/correct branches are
    implemented here. Drivers plug in by overriding ``_apply_curve`` and adding
    their own fields in ``_resolve_params``.
    """
    def __init__(self, config: MusicPitchCorrectorActionConfig, frame_period: float):
        self.config: MusicPitchCorrectorActionConfig = config
        self.frame_period: float = frame_period
        self.planner: MusicPitchCorrectionPlanner = MusicPitchCorrectionPlanner(frame_period)

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                results.extend(await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: MusicPitchCorrectorActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        """Resolve the per-method input tuple. Only slots the method actually
        consumes are included; the primary slot (``pitch`` for plan/correct,
        ``curve`` for apply) drives the batch dimension.
        """
        if method == MusicPitchCorrectorActionMethod.CORRECT:
            pitch         = await context.render_array(self.config.pitch, item_is_list=True, single_as_array=True)
            audio         = await context.render_audio(self.config.audio)
            key           = await context.render_array(self.config.key, item_is_list=False, single_as_array=True)
            scale         = self._resolve_scale(await context.render_variable(self.config.scale))
            melody        = await context.render_array(self.config.melody, item_is_list=True, single_as_array=True)
            melody_offset = await context.render_scalar(self.config.melody_offset, "time", 0.0)

            is_single_input    = isinstance(pitch, ArrayValue) and pitch.is_single
            is_streaming_input = isinstance(pitch, (StreamIterator, AsyncIterator))

            return (pitch, audio, key, scale, melody, melody_offset), is_single_input, is_streaming_input

        if method == MusicPitchCorrectorActionMethod.PLAN:
            pitch         = await context.render_array(self.config.pitch, item_is_list=True, single_as_array=True)
            key           = await context.render_array(self.config.key, item_is_list=False, single_as_array=True)
            scale         = self._resolve_scale(await context.render_variable(self.config.scale))
            melody        = await context.render_array(self.config.melody, item_is_list=True, single_as_array=True)
            melody_offset = await context.render_scalar(self.config.melody_offset, "time", 0.0)

            is_single_input    = isinstance(pitch, ArrayValue) and pitch.is_single
            is_streaming_input = isinstance(pitch, (StreamIterator, AsyncIterator))

            return (pitch, key, scale, melody, melody_offset), is_single_input, is_streaming_input

        if method == MusicPitchCorrectorActionMethod.APPLY:
            curve = await context.render_array(self.config.curve, item_is_list=False, single_as_array=True)
            audio = await context.render_audio(self.config.audio)

            is_single_input    = isinstance(curve, ArrayValue) and curve.is_single
            is_streaming_input = isinstance(curve, (StreamIterator, AsyncIterator))

            return (curve, audio), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported pitch correction method: {method}")

    async def _resolve_params(self, method: MusicPitchCorrectorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method in (MusicPitchCorrectorActionMethod.PLAN, MusicPitchCorrectorActionMethod.CORRECT):
            mode                 = await context.render_variable(self.config.mode)
            pitch_unit           = await context.render_variable(self.config.pitch_unit)
            align                = await context.render_variable(self.config.align)
            return_frames        = await context.render_scalar(self.config.return_frames, bool, True)
            strength             = await context.render_scalar(self.config.params.strength, float, 0.8)
            retune_speed         = await context.render_scalar(self.config.params.retune_speed, "time", 0.04)
            tolerance_cents      = await context.render_scalar(self.config.params.tolerance_cents, float, 10.0)
            max_correction_cents = await context.render_scalar(self.config.params.max_correction_cents, float, 250.0)
            out_of_range         = await context.render_variable(self.config.params.out_of_range)
            preserve_vibrato     = await context.render_scalar(self.config.params.preserve_vibrato, bool, True)
            transition           = await context.render_scalar(self.config.params.transition, "time", 0.06)
            min_note_duration    = await context.render_scalar(self.config.params.min_note_duration, "time", 0.08)
            min_confidence       = await context.render_scalar(self.config.params.min_confidence, float, 0.5)
            reference_pitch      = await context.render_scalar(self.config.params.reference_pitch, float, 440.0)

            try:
                mode = MusicPitchCorrectionMode(mode)
            except ValueError:
                raise ValueError(f"Invalid mode: {mode}")

            try:
                pitch_unit = PitchUnit(pitch_unit)
            except ValueError:
                raise ValueError(f"Invalid pitch_unit: {pitch_unit}")

            try:
                out_of_range = MusicPitchCorrectionOutOfRangeMode(out_of_range)
            except ValueError:
                raise ValueError(f"Invalid out_of_range: {out_of_range}")

            params: Dict[str, Any] = {
                "mode":                 mode,
                "pitch_unit":           pitch_unit,
                "align":                align,
                "return_frames":        return_frames,
                "strength":             strength,
                "retune_speed":         retune_speed,
                "tolerance_cents":      tolerance_cents,
                "max_correction_cents": max_correction_cents,
                "out_of_range":         out_of_range,
                "preserve_vibrato":     preserve_vibrato,
                "transition":           transition,
                "min_note_duration":    min_note_duration,
                "min_confidence":       min_confidence,
                "reference_pitch":      reference_pitch,
                "frame_period":         self.frame_period,
            }

            if method == MusicPitchCorrectorActionMethod.CORRECT:
                sample_rate  = await context.render_scalar(self.config.sample_rate, int)
                return_curve = await context.render_scalar(self.config.return_curve, bool, False)

                params.update({
                    "sample_rate":  sample_rate,
                    "return_curve": return_curve,
                })

            return params

        if method == MusicPitchCorrectorActionMethod.APPLY:
            sample_rate = await context.render_scalar(self.config.sample_rate, int)

            return {
                "sample_rate":  sample_rate,
                "frame_period": self.frame_period,
            }

        raise ValueError(f"Unsupported pitch correction method: {method}")

    async def _process_batch(
        self,
        method: MusicPitchCorrectorActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        inputs = list(zip(*inputs))

        return await asyncio.gather(*[
            self._process(method, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: MusicPitchCorrectorActionMethod,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if method == MusicPitchCorrectorActionMethod.CORRECT:
            pitch, audio, key, scale, melody, melody_offset = input

            if isinstance(pitch, ArrayValue):
                pitch = await pitch.collect()

            if isinstance(key, ArrayValue):
                key = (await key.collect())[0]

            if isinstance(scale, ArrayValue):
                collected = await scale.collect()
                scale = collected[0] if len(collected) == 1 else collected

            if isinstance(scale, str):
                try:
                    scale = MusicPitchCorrectionScale(scale)
                except ValueError:
                    raise ValueError(f"Invalid scale: {scale}")

            if isinstance(scale, MusicPitchCorrectionScale):
                scale = _SCALE_PRESETS[scale]

            if isinstance(melody, ArrayValue):
                melody = await melody.collect()

            if params["mode"] == MusicPitchCorrectionMode.SCALE and not key:
                raise ValueError("`mode: scale` requires a non-empty `key`.")

            if params["mode"] == MusicPitchCorrectionMode.MELODY and melody is None:
                raise ValueError("`mode: melody` requires a non-empty `melody`.")

            return await self._correct(pitch, audio, key, scale, melody, melody_offset, params)

        if method == MusicPitchCorrectorActionMethod.PLAN:
            pitch, key, scale, melody, melody_offset = input

            if isinstance(pitch, ArrayValue):
                pitch = await pitch.collect()

            if isinstance(key, ArrayValue):
                key = (await key.collect())[0]

            if isinstance(scale, ArrayValue):
                collected = await scale.collect()
                scale = collected[0] if len(collected) == 1 else collected

            if isinstance(scale, str):
                try:
                    scale = MusicPitchCorrectionScale(scale)
                except ValueError:
                    raise ValueError(f"Invalid scale: {scale}")

            if isinstance(scale, MusicPitchCorrectionScale):
                scale = _SCALE_PRESETS[scale]

            if isinstance(melody, ArrayValue):
                melody = await melody.collect()

            if params["mode"] == MusicPitchCorrectionMode.SCALE and not key:
                raise ValueError("`mode: scale` requires a non-empty `key`.")

            if params["mode"] == MusicPitchCorrectionMode.MELODY and melody is None:
                raise ValueError("`mode: melody` requires a non-empty `melody`.")

            return await self._plan(pitch, key, scale, melody, melody_offset, params)

        if method == MusicPitchCorrectorActionMethod.APPLY:
            curve, audio = input

            if isinstance(curve, ArrayValue):
                curve = (await curve.collect())[0]

            if not isinstance(curve, dict):
                raise ValueError("`curve` must be a dict produced by the `plan` method.")

            if "notes" not in curve:
                raise ValueError("`curve` is missing required `notes` field.")

            return await self._apply(curve, audio, params)

        raise ValueError(f"Unsupported pitch correction method: {method}")

    async def _correct(
        self,
        pitch: Any,
        audio: MediaSource,
        key: Optional[str],
        scale: Any,
        melody: Any,
        melody_offset: float,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        f0_semitones, confidence, time_axis, voiced_mask = self._decode_pitch_frames(
            pitch,
            params["pitch_unit"].value,
            params["reference_pitch"],
        )

        curve, report = await self._run_in_executor(
            self.planner.plan,
            f0_semitones,
            confidence,
            time_axis,
            voiced_mask,
            key,
            scale,
            melody,
            melody_offset,
            params,
        )

        samples, sample_rate = await self._load_pcm_samples(audio)
        output_samples = await self._apply_curve(
            samples, sample_rate, curve, params,
        )

        apply_report = self._build_apply_report(curve)
        report["notes_corrected"] = apply_report["notes_corrected"]

        result: Dict[str, Any] = {
            "audio":  self._stream_output(output_samples, params.get("sample_rate") or sample_rate),
            "report": MusicPitchCorrectionReport(report),
        }

        if params.get("return_curve"):
            result["curve"] = MusicPitchCorrectionCurve(curve)

        return result

    async def _plan(
        self,
        pitch: Any,
        key: Optional[str],
        scale: Any,
        melody: Any,
        melody_offset: float,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        f0_semitones, confidence, time_axis, voiced_mask = self._decode_pitch_frames(
            pitch,
            params["pitch_unit"].value,
            params["reference_pitch"],
        )

        curve, report = await self._run_in_executor(
            self.planner.plan,
            f0_semitones,
            confidence,
            time_axis,
            voiced_mask,
            key,
            scale,
            melody,
            melody_offset,
            params,
        )

        return {
            "curve":  MusicPitchCorrectionCurve(curve),
            "report": MusicPitchCorrectionReport(report),
        }

    async def _apply(self, curve: Any, audio: MediaSource, params: Dict[str, Any]) -> Dict[str, Any]:
        samples, sample_rate = await self._load_pcm_samples(audio)
        self._validate_curve_length(curve, samples.shape[-1], sample_rate)

        output_samples = await self._apply_curve(samples, sample_rate, curve, params)

        return {
            "audio":  self._stream_output(output_samples, params.get("sample_rate") or sample_rate),
            "report": MusicPitchCorrectionReport(self._build_apply_report(curve)),
        }

    async def _load_pcm_samples(self, source: MediaSource) -> Tuple[np.ndarray, int]:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        try:
            if input_path is None:
                audio = await read_stream_to_buffer(source.stream)
            else:
                audio = input_path

            return await self._run_in_executor(load_pcm_samples, audio, True, None)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    def _resolve_scale(self, scale: Any) -> Any:
        """``render_array`` can't disambiguate scale on its own: the single
        form may itself be a ``List[int]`` (pitch-class list) and a batch may
        contain non-list scale names (``['major', 'minor']``). Dispatch here —
        list of lists/strs is a batch; everything else is a broadcast
        ``ArrayValue``.
        """
        if scale is None or isinstance(scale, (StreamIterator, AsyncIterator)):
            return scale

        if isinstance(scale, list) and scale and isinstance(scale[0], (list, str)):
            return scale

        return ArrayValue([ scale ] if not isinstance(scale, list) else scale, is_single=True)

    def _decode_pitch_frames(self, frames: List[Dict[str, Any]], pitch_unit: str, reference_pitch: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Normalize music-pitch-estimation frames into the internal
        ``(f0_semitones, confidence, time_axis, voiced_mask)`` tuple.
        """
        import numpy as np

        if not frames:
            raise ValueError("`pitch.frames` is empty.")

        pitch_values = np.asarray([ frame["pitch"] for frame in frames ], dtype=np.float32)
        time_values  = np.asarray([ frame["time"]  for frame in frames ], dtype=np.float32)
        confidence   = np.asarray([ frame.get("confidence", 1.0) for frame in frames ], dtype=np.float32)

        if pitch_unit == "semitone":
            semitones = pitch_values.copy()
        elif pitch_unit == "hz":
            with np.errstate(divide="ignore", invalid="ignore"):
                semitones = np.where(
                    pitch_values > 0.0,
                    12.0 * np.log2(pitch_values / reference_pitch) + 69.0,
                    np.nan,
                )
        else:
            raise ValueError(f"Unsupported `pitch_unit`: {pitch_unit!r}")

        voiced_mask = np.isfinite(semitones) & (confidence > 0.0)
        semitones = np.where(voiced_mask, semitones, np.nan)

        return semitones.astype(np.float32), confidence.astype(np.float32), time_values.astype(np.float32), voiced_mask

    def _validate_curve_length(self, curve: Dict[str, Any], num_samples: int, sample_rate: int) -> None:
        frames = curve.get("frames") or {}
        time_axis = frames.get("time") or []

        if not time_axis:
            return

        curve_duration = float(time_axis[-1]) + float(curve.get("frame_period", self.frame_period))
        audio_duration = num_samples / sample_rate

        if audio_duration <= 0.0:
            raise ValueError("Audio has non-positive duration.")

        drift = abs(curve_duration - audio_duration) / audio_duration

        if drift > 0.05:
            raise ValueError(
                f"Curve length ({curve_duration:.3f}s) differs from audio length "
                f"({audio_duration:.3f}s) by {drift * 100:.1f}% — this looks like a mismatched recording."
            )

    def _build_apply_report(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        notes = curve.get("notes", [])
        corrected = [n for n in notes if n.get("status") == "corrected" and n.get("target_pitch") is not None]

        return {
            "notes_total":     len(notes),
            "notes_corrected": len(corrected),
            "warnings":        [],
        }

    def _stream_output(self, waveform: np.ndarray, sample_rate: int) -> AudioBufferStreamIterator:
        """Chunk the already-synthesized waveform into AudioBuffers so
        downstream consumers (mixer, player, HTTP response) can start writing
        before the full tail arrives.
        """
        import numpy as np

        waveform = np.asarray(waveform)
        channels = 1 if waveform.ndim == 1 else int(waveform.shape[0] if waveform.shape[0] < waveform.shape[1] else waveform.shape[1])
        chunk_samples = max(1, int(sample_rate * _STREAM_CHUNK_SECONDS))

        async def _stream() -> AsyncIterator[AudioBuffer]:
            length = waveform.shape[-1]
            offset = 0

            while offset < length:
                end = min(offset + chunk_samples, length)

                if waveform.ndim == 1:
                    yield AudioBuffer(waveform=waveform[offset:end], sample_rate=sample_rate)
                else:
                    yield AudioBuffer(waveform=waveform[..., offset:end], sample_rate=sample_rate)

                offset = end

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=sample_rate,
            channels=channels,
        )

    @abstractmethod
    async def _apply_curve(
        self,
        samples: np.ndarray,
        sample_rate: int,
        curve: Dict[str, Any],
        params: Dict[str, Any],
    ) -> np.ndarray:
        """Driver-specific resynthesis. ``params`` holds the merged apply-time
        params (``sample_rate`` + whatever the driver added by overriding
        ``_resolve_params``).
        """
        pass
