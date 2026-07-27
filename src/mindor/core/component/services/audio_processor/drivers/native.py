from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import AudioProcessorComponentConfig
from mindor.dsl.schema.action import AudioProcessorActionConfig, AudioProcessorNormalizeMode, AudioProcessorPeakLimitMode
from mindor.core.utils.audio import AudioBuffer
from ..base import AudioProcessorService, AudioProcessorDriver, register_audio_processor_service
from ..base import ComponentActionContext
from .common import AudioProcessorAction

if TYPE_CHECKING:
    import numpy as np

class NativeAudioProcessorAction(AudioProcessorAction):
    async def _resample(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _resample() -> AudioBuffer:
            import numpy as np
            import soxr

            waveform = np.asarray(audio.waveform, dtype=np.float32)
            target_sample_rate = int(params["sample_rate"])

            if target_sample_rate == audio.sample_rate:
                return AudioBuffer(waveform, audio.sample_rate)

            waveform = soxr.resample(waveform, audio.sample_rate, target_sample_rate, quality="HQ")

            return AudioBuffer(waveform, target_sample_rate)

        return await self._run_in_executor(_resample)

    async def _highpass(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _highpass() -> AudioBuffer:
            from pedalboard import Pedalboard, HighpassFilter

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                HighpassFilter(cutoff_frequency_hz=params["cutoff"]),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_highpass)

    async def _lowpass(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _lowpass() -> AudioBuffer:
            from pedalboard import Pedalboard, LowpassFilter

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                LowpassFilter(cutoff_frequency_hz=params["cutoff"]),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_lowpass)

    async def _bell(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _bell() -> AudioBuffer:
            from pedalboard import Pedalboard, PeakFilter

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                PeakFilter(
                    cutoff_frequency_hz=params["frequency"],
                    gain_db=params["gain"],
                    q=params["q"],
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_bell)

    async def _low_shelf(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _low_shelf() -> AudioBuffer:
            from pedalboard import Pedalboard, LowShelfFilter

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                LowShelfFilter(
                    cutoff_frequency_hz=params["frequency"],
                    gain_db=params["gain"],
                    q=params["q"],
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_low_shelf)

    async def _high_shelf(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _high_shelf() -> AudioBuffer:
            from pedalboard import Pedalboard, HighShelfFilter

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                HighShelfFilter(
                    cutoff_frequency_hz=params["frequency"],
                    gain_db=params["gain"],
                    q=params["q"],
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_high_shelf)

    async def _pitch_shift(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _pitch_shift() -> AudioBuffer:
            from pedalboard import Pedalboard, PitchShift

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                PitchShift(semitones=params["semitones"]),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_pitch_shift)

    async def _dc_shift(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _dc_shift() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32)

            if waveform.size > 0:
                waveform = waveform - float(np.mean(waveform)) + params["offset"]

            return AudioBuffer(waveform, audio.sample_rate)

        return await self._run_in_executor(_dc_shift)

    async def _compressor(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _compressor() -> AudioBuffer:
            from pedalboard import Pedalboard, Compressor

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Compressor(
                    threshold_db=params["threshold"],
                    ratio=params["ratio"],
                    attack_ms=params["attack"] * 1000.0,
                    release_ms=params["release"] * 1000.0,
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_compressor)

    async def _noise_gate(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _noise_gate() -> AudioBuffer:
            from pedalboard import Pedalboard, NoiseGate

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                NoiseGate(
                    threshold_db=params["threshold"],
                    ratio=params["ratio"],
                    attack_ms=params["attack"] * 1000.0,
                    release_ms=params["release"] * 1000.0,
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_noise_gate)

    async def _distortion(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _distortion() -> AudioBuffer:
            from pedalboard import Pedalboard, Distortion

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Distortion(drive_db=params["drive"]),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_distortion)

    async def _saturation(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _saturation() -> AudioBuffer:
            from pedalboard import Pedalboard, Distortion

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Distortion(drive_db=params["drive"]),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_saturation)

    async def _gain(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _gain() -> AudioBuffer:
            from pedalboard import Pedalboard, Gain

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Gain(gain_db=params["level"]),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_gain)

    async def _chorus(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _chorus() -> AudioBuffer:
            from pedalboard import Pedalboard, Chorus

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Chorus(
                    rate_hz=params["rate"],
                    depth=params["depth"],
                    feedback=params["feedback"],
                    centre_delay_ms=params["delay"] * 1000.0,
                    mix=params["mix"],
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_chorus)

    async def _delay(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _delay() -> AudioBuffer:
            from pedalboard import Pedalboard, Delay

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Delay(
                    delay_seconds=params["time"],
                    feedback=params["feedback"],
                    mix=params["mix"],
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_delay)

    async def _reverb(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _reverb() -> AudioBuffer:
            from pedalboard import Pedalboard, Reverb

            waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
                Reverb(
                    room_size=params["room_size"],
                    damping=params["damping"],
                    wet_level=params["wet_level"],
                    dry_level=params["dry_level"],
                    width=params["width"],
                ),
            ]))

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_reverb)

    async def _normalize(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _normalize() -> AudioBuffer:
            if params["mode"] == AudioProcessorNormalizeMode.RMS:
                return self._normalize_rms(audio, params)

            if params["mode"] == AudioProcessorNormalizeMode.PEAK:
                return self._normalize_peak(audio, params)

            if params["mode"] == AudioProcessorNormalizeMode.LUFS:
                return self._normalize_lufs(audio, params)

            raise ValueError(f"Unsupported normalize mode: {params['mode']}")

        return await self._run_in_executor(_normalize)

    async def _peak_limit(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _peak_limit() -> AudioBuffer:
            if params["mode"] == AudioProcessorPeakLimitMode.HARD:
                return self._peak_limit_hard(audio, params)

            if params["mode"] == AudioProcessorPeakLimitMode.SMOOTH:
                return self._peak_limit_smooth(audio, params)

            raise ValueError(f"Unsupported peak-limit mode: {params['mode']}")

        return await self._run_in_executor(_peak_limit)

    async def _trim_edges(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _trim_edges() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32)
            sample_rate = audio.sample_rate

            frame_length = 2048
            hop_length = 512
            trimmed = waveform

            if waveform.size >= frame_length:
                frames = np.lib.stride_tricks.sliding_window_view(waveform, frame_length)[::hop_length]
                rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))

                ref = float(np.max(rms))
                if ref > 0:
                    threshold_linear = ref * (10.0 ** (-params["threshold"] / 20.0))
                    non_silent = rms > threshold_linear

                    if np.any(non_silent):
                        start_frame = int(np.argmax(non_silent))
                        end_frame = int(len(non_silent) - np.argmax(non_silent[::-1]))
                        start_sample = start_frame * hop_length
                        end_sample = min(end_frame * hop_length + frame_length, waveform.size)
                        trimmed = waveform[start_sample:end_sample]
                    else:
                        trimmed = waveform[:0]

            if 0 < trimmed.size < waveform.size:
                pad_each = int(sample_rate * params["padding"])
                headroom = (waveform.size - trimmed.size) // 2
                pad = min(pad_each, max(headroom, 0))
                if pad > 0:
                    trimmed = np.pad(trimmed, (pad, pad), mode="constant")

            return AudioBuffer(trimmed, sample_rate)

        return await self._run_in_executor(_trim_edges)

    async def _trim_silence(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _trim_silence() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32)
            sample_rate = audio.sample_rate

            window_seconds = params["window"]
            frame_len = int(sample_rate * window_seconds)
            if frame_len == 0 or len(waveform) < frame_len:
                return AudioBuffer(waveform, sample_rate)

            n_frames = len(waveform) // frame_len
            threshold_linear = 10.0 ** (params["threshold"] / 20.0)

            rms = np.array([
                np.sqrt(np.mean(waveform[i * frame_len : (i + 1) * frame_len] ** 2))
                for i in range(n_frames)
            ])
            is_speech = rms >= threshold_linear

            first_speech = 0
            for i, s in enumerate(is_speech):
                if s:
                    first_speech = max(0, i - 1)
                    break

            max_silence_frames = int(params["max_internal_silence"] / window_seconds) if window_seconds > 0 else n_frames
            consecutive_silence = 0
            cut_frame = n_frames

            for i in range(first_speech, n_frames):
                if is_speech[i]:
                    consecutive_silence = 0
                else:
                    consecutive_silence += 1
                    if consecutive_silence >= max_silence_frames:
                        cut_frame = i - consecutive_silence + 1
                        break

            min_silence_frames = int(params["min_silence"] / window_seconds) if window_seconds > 0 else 0
            end_frame = cut_frame
            while end_frame > first_speech and not is_speech[end_frame - 1]:
                end_frame -= 1
            end_frame = min(end_frame + min_silence_frames, cut_frame)

            start_sample = first_speech * frame_len
            end_sample = min(end_frame * frame_len, len(waveform))

            trimmed = waveform[start_sample:end_sample].copy()

            fade_samples = int(sample_rate * params["fade"])
            if fade_samples > 0 and len(trimmed) > fade_samples:
                fade = np.cos(np.linspace(0, np.pi / 2, fade_samples)) ** 2
                trimmed[-fade_samples:] *= fade

            return AudioBuffer(trimmed, sample_rate)

        return await self._run_in_executor(_trim_silence)

    async def _fade_in(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _fade_in() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32).copy()
            sample_rate = audio.sample_rate

            fade_samples = int(sample_rate * params["duration"])

            if fade_samples > 0 and waveform.size > fade_samples:
                fade = np.sin(np.linspace(0, np.pi / 2, fade_samples)) ** 2

                if waveform.ndim == 1:
                    waveform[:fade_samples] *= fade
                else:
                    waveform[:, :fade_samples] *= fade

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_fade_in)

    async def _fade_out(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        def _fade_out() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32).copy()
            sample_rate = audio.sample_rate

            fade_samples = int(sample_rate * params["duration"])

            if fade_samples > 0 and waveform.size > fade_samples:
                fade = np.cos(np.linspace(0, np.pi / 2, fade_samples)) ** 2
                if waveform.ndim == 1:
                    waveform[-fade_samples:] *= fade
                else:
                    waveform[:, -fade_samples:] *= fade

            return AudioBuffer(waveform, sample_rate)

        return await self._run_in_executor(_fade_out)

    def _normalize_rms(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        rms = float(np.sqrt(np.mean(waveform ** 2)))
        target_rms = 10.0 ** (params["level"] / 20.0)

        if rms > 0:
            waveform = waveform * (target_rms / rms)

        peak_limit = params["peak_limit"]
        waveform = np.clip(waveform, -peak_limit, peak_limit)

        return AudioBuffer(waveform, audio.sample_rate)

    def _normalize_peak(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        peak = float(np.abs(waveform).max()) if waveform.size > 0 else 0.0
        target_peak = 10.0 ** (params["level"] / 20.0)

        if peak > 0:
            waveform = waveform * (target_peak / peak)

        return AudioBuffer(waveform, audio.sample_rate)

    def _normalize_lufs(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        from pedalboard import Pedalboard, Resample, Limiter
        import pyloudnorm as pyln
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        sample_rate = audio.sample_rate

        target_lufs       = params["level"]
        tolerance         = params["tolerance"]
        max_gain          = params["max_gain"]
        true_peak_ceiling = params["true_peak_ceiling"]

        audio_2d = waveform[np.newaxis, :] if waveform.ndim == 1 else waveform
        meter_input = audio_2d[0] if audio_2d.shape[0] == 1 else audio_2d.T

        meter = pyln.Meter(sample_rate)
        applied_gain_db = 0.0

        for _ in range(3):
            measured = meter.integrated_loudness(meter_input.astype(np.float64))
            if not np.isfinite(measured):
                break

            delta = target_lufs - measured
            if abs(delta) <= tolerance:
                break

            remaining_headroom = max_gain - abs(applied_gain_db)
            if remaining_headroom <= 0:
                break

            step = float(np.clip(delta, -remaining_headroom, remaining_headroom))
            gain_linear = 10.0 ** (step / 20.0)
            audio_2d = audio_2d * gain_linear
            meter_input = audio_2d[0] if audio_2d.shape[0] == 1 else audio_2d.T
            applied_gain_db += step

        oversample = 4
        adjusted = audio_2d[0] if waveform.ndim == 1 else audio_2d

        processed_waveform, processed_sample_rate = self._apply_board(adjusted, sample_rate, Pedalboard([
            Resample(target_sample_rate=sample_rate * oversample, quality=Resample.Quality.WindowedSinc),
            Limiter(threshold_db=true_peak_ceiling, release_ms=100.0),
            Resample(target_sample_rate=sample_rate, quality=Resample.Quality.WindowedSinc),
        ]))

        return AudioBuffer(processed_waveform, processed_sample_rate)

    def _peak_limit_hard(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)

        if waveform.size > 0:
            limit = params["level"]
            peak = float(np.abs(waveform).max())
            if peak > limit and peak > 0:
                waveform = waveform * (limit / peak)

        return AudioBuffer(waveform, audio.sample_rate)

    def _peak_limit_smooth(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        from pedalboard import Pedalboard, Limiter

        waveform, sample_rate = self._apply_board(audio.waveform, audio.sample_rate, Pedalboard([
            Limiter(
                threshold_db=params["level"],
                release_ms=params["release"] * 1000.0,
            ),
        ]))

        return AudioBuffer(waveform, sample_rate)

    def _apply_board(self, waveform: np.ndarray, sample_rate: int, board: Any) -> Tuple[np.ndarray, int]:
        import numpy as np

        waveform = np.asarray(waveform, dtype=np.float32)
        audio_2d = waveform[np.newaxis, :] if waveform.ndim == 1 else waveform
        processed = board(audio_2d, sample_rate)

        return (processed[0] if waveform.ndim == 1 else processed), sample_rate

@register_audio_processor_service(AudioProcessorDriver.NATIVE)
class NativeAudioProcessorService(AudioProcessorService):
    def __init__(self, id: str, config: AudioProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pedalboard", "numpy", "torchaudio", "soxr", "pyloudnorm" ]

    async def _run(self, action: AudioProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await NativeAudioProcessorAction(action).run(context)
