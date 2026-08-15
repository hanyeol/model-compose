from __future__ import annotations

from typing import Optional, Dict, List, Any, TYPE_CHECKING
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioProcessorComponentConfig

if TYPE_CHECKING:
    import numpy as np
from mindor.dsl.schema.action import AudioProcessorActionConfig, AudioProcessorNormalizeMode, AudioProcessorPeakLimitMode
from mindor.core.utils.audio import AudioBuffer
from mindor.core.foundation.streaming.audio import AudioBufferStreamIterator
from ..base import AudioProcessorService, AudioProcessorDriver, register_audio_processor_service
from ..base import ComponentActionContext
from .common import AudioProcessorAction

class NativeAudioProcessorAction(AudioProcessorAction):
    async def _resample(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        import numpy as np
        import soxr

        # soxr expects (samples, channels) interleaved; keep it that way per chunk.
        resampler = soxr.ResampleStream(audio.sample_rate, params["sample_rate"], num_channels=audio.channels, dtype="float32")
        keep_channels = audio.channels > 1

        def _process(waveform, last: bool):
            samples = waveform.T if keep_channels else waveform
            resampled = resampler.resample_chunk(samples, last=last)
            return resampled.T if keep_channels else resampled

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                resampled = await self._run_in_executor(_process, chunk.waveform, False)
                if resampled.shape[-1] > 0:
                    yield AudioBuffer(resampled, params["sample_rate"])

            tail = await self._run_in_executor(_process, np.zeros((audio.channels, 0), dtype=np.float32) if keep_channels else np.zeros(0, dtype=np.float32), True)
            if tail.shape[-1] > 0:
                yield AudioBuffer(tail, params["sample_rate"])

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=params["sample_rate"],
            channels=audio.channels,
        )

    async def _highpass(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, HighpassFilter
        import numpy as np

        board = Pedalboard([ HighpassFilter(cutoff_frequency_hz=params["cutoff"]) ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _lowpass(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, LowpassFilter
        import numpy as np

        board = Pedalboard([ LowpassFilter(cutoff_frequency_hz=params["cutoff"]) ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _bell(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, PeakFilter
        import numpy as np

        board = Pedalboard([
            PeakFilter(cutoff_frequency_hz=params["frequency"], gain_db=params["gain"], q=params["q"]),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _low_shelf(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, LowShelfFilter
        import numpy as np

        board = Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=params["frequency"], gain_db=params["gain"], q=params["q"]),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _high_shelf(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, HighShelfFilter
        import numpy as np

        board = Pedalboard([
            HighShelfFilter(cutoff_frequency_hz=params["frequency"], gain_db=params["gain"], q=params["q"]),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _pitch_shift(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, PitchShift
        import numpy as np

        board = Pedalboard([ PitchShift(semitones=params["semitones"]) ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            pending = 0
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                pending += chunk.waveform.shape[-1] - processed.shape[-1]
                if processed.shape[-1] > 0:
                    yield AudioBuffer(processed, audio.sample_rate)

            # Drain pedalboard's lookahead by feeding zeros, doubling the chunk
            # until it releases enough to match what we consumed.
            padding = max(pending, 1)
            while pending > 0:
                zeros = np.zeros((audio.channels, padding), dtype=np.float32) if keep_channels else np.zeros(padding, dtype=np.float32)
                tail = await self._run_in_executor(_process, zeros)
                if tail.shape[-1] == 0:
                    padding *= 2
                    continue
                trim = min(tail.shape[-1], pending)
                yield AudioBuffer(tail[..., :trim], audio.sample_rate)
                pending -= trim

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _dc_shift(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        # Needs the global mean → collect.
        audio = await audio.collect()

        def _dc_shift() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32)

            if waveform.size > 0:
                waveform = waveform - float(np.mean(waveform)) + params["offset"]

            return AudioBuffer(waveform, audio.sample_rate)

        return AudioBufferStreamIterator.from_single(await self._run_in_executor(_dc_shift))

    async def _compressor(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Compressor
        import numpy as np

        board = Pedalboard([
            Compressor(
                threshold_db=params["threshold"],
                ratio=params["ratio"],
                attack_ms=params["attack_time"] * 1000.0,
                release_ms=params["release_time"] * 1000.0,
            ),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _noise_gate(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, NoiseGate
        import numpy as np

        board = Pedalboard([
            NoiseGate(
                threshold_db=params["threshold"],
                ratio=params["ratio"],
                attack_ms=params["attack_time"] * 1000.0,
                release_ms=params["release_time"] * 1000.0,
            ),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _distortion(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Distortion
        import numpy as np

        board = Pedalboard([ Distortion(drive_db=params["drive"]) ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _saturation(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Distortion
        import numpy as np

        board = Pedalboard([ Distortion(drive_db=params["drive"]) ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _gain(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Gain
        import numpy as np

        board = Pedalboard([ Gain(gain_db=params["level"]) ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _chorus(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Chorus
        import numpy as np

        board = Pedalboard([
            Chorus(
                rate_hz=params["rate"],
                depth=params["depth"],
                feedback=params["feedback"],
                centre_delay_ms=params["delay"] * 1000.0,
                mix=params["mix"],
            ),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _delay(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Delay
        import numpy as np

        board = Pedalboard([
            Delay(
                delay_seconds=params["time"],
                feedback=params["feedback"],
                mix=params["mix"],
            ),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _reverb(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        from pedalboard import Pedalboard, Reverb
        import numpy as np

        board = Pedalboard([
            Reverb(
                room_size=params["room_size"],
                damping=params["damping"],
                wet_level=params["wet_level"],
                dry_level=params["dry_level"],
                width=params["width"],
            ),
        ])
        keep_channels = audio.channels > 1

        def _process(waveform):
            audio_2d = waveform if keep_channels else waveform[np.newaxis, :]
            processed = board(audio_2d, audio.sample_rate, reset=False)
            return processed if keep_channels else processed[0]

        async def _stream() -> AsyncIterator[AudioBuffer]:
            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform)
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _normalize(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        # Needs global statistics (RMS / peak / LUFS) → collect.
        audio = await audio.collect()

        def _normalize() -> AudioBuffer:
            if params["mode"] == AudioProcessorNormalizeMode.RMS:
                return self._normalize_rms(audio, params["level"], params["peak_limit"])

            if params["mode"] == AudioProcessorNormalizeMode.PEAK:
                return self._normalize_peak(audio, params["level"])

            if params["mode"] == AudioProcessorNormalizeMode.LUFS:
                return self._normalize_lufs(
                    audio,
                    params["level"],
                    params["tolerance"],
                    params["max_gain"],
                    params["true_peak_ceiling"],
                )

            raise ValueError(f"Unsupported normalize mode: {params['mode']}")

        return AudioBufferStreamIterator.from_single(await self._run_in_executor(_normalize))

    async def _peak_limit(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        # Needs the global peak (HARD) or shared dispatch with SMOOTH → collect.
        audio = await audio.collect()

        def _peak_limit() -> AudioBuffer:
            if params["mode"] == AudioProcessorPeakLimitMode.HARD:
                return self._peak_limit_hard(audio, params["level"])

            if params["mode"] == AudioProcessorPeakLimitMode.SMOOTH:
                return self._peak_limit_smooth(audio, params["level"], params["release_time"])

            raise ValueError(f"Unsupported peak-limit mode: {params['mode']}")

        return AudioBufferStreamIterator.from_single(await self._run_in_executor(_peak_limit))

    async def _trim_edges(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        # Needs the whole signal to locate silence at both edges → collect.
        audio = await audio.collect()

        def _trim_edges() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32)

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
                pad_each = int(audio.sample_rate * params["padding"])
                headroom = (waveform.size - trimmed.size) // 2
                pad = min(pad_each, max(headroom, 0))
                if pad > 0:
                    trimmed = np.pad(trimmed, (pad, pad), mode="constant")

            return AudioBuffer(trimmed, audio.sample_rate)

        return AudioBufferStreamIterator.from_single(await self._run_in_executor(_trim_edges))

    async def _trim_silence(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        # Needs the whole signal to locate silence boundaries → collect.
        audio = await audio.collect()

        def _trim_silence() -> AudioBuffer:
            import numpy as np

            waveform = np.asarray(audio.waveform, dtype=np.float32)

            window_seconds = params["window"]
            frame_length = int(audio.sample_rate * window_seconds)

            if frame_length == 0 or len(waveform) < frame_length:
                return AudioBuffer(waveform, audio.sample_rate)

            n_frames = len(waveform) // frame_length
            threshold_linear = 10.0 ** (params["threshold"] / 20.0)

            rms = np.array([
                np.sqrt(np.mean(waveform[frame * frame_length : (frame + 1) * frame_length] ** 2))
                for frame in range(n_frames)
            ])
            is_speeches = rms >= threshold_linear

            first_speech = 0
            for frame, is_speech in enumerate(is_speeches):
                if is_speech:
                    first_speech = max(0, frame - 1)
                    break

            max_silence_frames = int(params["max_internal_silence"] / window_seconds) if window_seconds > 0 else n_frames
            consecutive_silence = 0
            cut_frame = n_frames

            for frame in range(first_speech, n_frames):
                if is_speeches[frame]:
                    consecutive_silence = 0
                else:
                    consecutive_silence += 1
                    if consecutive_silence >= max_silence_frames:
                        cut_frame = frame - consecutive_silence + 1
                        break

            min_silence_frames = int(params["min_silence"] / window_seconds) if window_seconds > 0 else 0
            end_frame = cut_frame

            while end_frame > first_speech and not is_speeches[end_frame - 1]:
                end_frame -= 1

            end_frame = min(end_frame + min_silence_frames, cut_frame)

            start_sample = first_speech * frame_length
            end_sample = min(end_frame * frame_length, len(waveform))

            trimmed = waveform[start_sample:end_sample].copy()

            fade_samples = int(audio.sample_rate * params["fade"])

            if fade_samples > 0 and len(trimmed) > fade_samples:
                fade = np.cos(np.linspace(0, np.pi / 2, fade_samples)) ** 2
                trimmed[-fade_samples:] *= fade

            return AudioBuffer(trimmed, audio.sample_rate)

        return AudioBufferStreamIterator.from_single(await self._run_in_executor(_trim_silence))

    async def _fade_in(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        import numpy as np

        fade_samples = int(audio.sample_rate * params["duration"])
        fade_curve = np.sin(np.linspace(0, np.pi / 2, fade_samples)) ** 2 if fade_samples > 0 else None
        keep_channels = audio.channels > 1

        # Track how many samples we've emitted so we know which slice of the fade
        # curve to apply to each incoming chunk.
        position = 0

        def _process(waveform, pos):
            length = waveform.shape[-1]

            if fade_curve is None or pos >= fade_samples or length == 0:
                return waveform

            waveform = waveform.copy()
            end = min(pos + length, fade_samples)
            window = fade_curve[pos:end]

            if keep_channels:
                waveform[:, :window.size] *= window
            else:
                waveform[:window.size] *= window

            return waveform

        async def _stream() -> AsyncIterator[AudioBuffer]:
            nonlocal position

            async for chunk in audio:
                processed = await self._run_in_executor(_process, chunk.waveform, position)
                position += chunk.waveform.shape[-1]
                yield AudioBuffer(processed, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _fade_out(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        import numpy as np

        fade_samples = int(audio.sample_rate * params["duration"])
        fade_curve = np.cos(np.linspace(0, np.pi / 2, fade_samples)) ** 2 if fade_samples > 0 else None
        keep_channels = audio.channels > 1

        # Hold back the last `fade_samples` so we can apply the curve on flush;
        # emit anything older than that as we go.
        tail = np.zeros((audio.channels, 0), dtype=np.float32) if keep_channels else np.zeros(0, dtype=np.float32)

        async def _stream() -> AsyncIterator[AudioBuffer]:
            nonlocal tail

            async for chunk in audio:
                if fade_curve is None:
                    yield chunk
                    continue

                combined = np.concatenate([ tail, chunk.waveform ], axis=-1)
                excess = combined.shape[-1] - fade_samples

                if excess > 0:
                    emit = combined[..., :excess]
                    tail = combined[..., excess:]
                    yield AudioBuffer(emit, audio.sample_rate)
                else:
                    tail = combined

            if tail.shape[-1] > 0:
                if fade_curve is not None:
                    window = fade_curve[-tail.shape[-1]:]
                    tail = tail.copy()
                    if keep_channels:
                        tail *= window
                    else:
                        tail *= window
                yield AudioBuffer(tail, audio.sample_rate)

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )

    async def _anonymize(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        # Needs the whole signal for time-varying jitter and formant warping → collect.
        audio = await audio.collect()

        def _anonymize() -> AudioBuffer:
            import numpy as np
            import librosa

            waveform = np.asarray(audio.waveform, dtype=np.float32)
            
            if waveform.size == 0:
                return AudioBuffer(waveform, audio.sample_rate)

            channels = waveform if waveform.ndim == 2 else waveform[np.newaxis, :]

            rng = np.random.default_rng(params["seed"])
            n_fft = 2048
            hop_length = 512
            processed_channels = []

            for channel in channels:
                shifted = librosa.effects.pitch_shift(
                    channel.astype(np.float32),
                    sr=audio.sample_rate,
                    n_steps=params["pitch_shift"],
                )

                if params["pitch_jitter"] > 0:
                    shifted = self._apply_pitch_jitter(
                        shifted,
                        audio.sample_rate,
                        params["pitch_jitter"],
                        params["jitter_rate"],
                        rng,
                        n_fft,
                    )

                if params["formant_shift"] and params["formant_shift"] != 1.0:
                    shifted = self._shift_formants(shifted, params["formant_shift"], n_fft, hop_length)

                processed_channels.append(shifted.astype(np.float32))

            result = np.stack(processed_channels, axis=0) if waveform.ndim == 2 else processed_channels[0]

            if params["lowpass_cutoff"] is not None and params["lowpass_cutoff"] > 0:
                from pedalboard import Pedalboard, LowpassFilter

                board = Pedalboard([ LowpassFilter(cutoff_frequency_hz=params["lowpass_cutoff"]) ])
                result_2d = result if result.ndim == 2 else result[np.newaxis, :]
                filtered = board(result_2d, audio.sample_rate)
                result = filtered[0] if result.ndim == 1 else filtered

            return AudioBuffer(result, audio.sample_rate)

        return AudioBufferStreamIterator.from_single(await self._run_in_executor(_anonymize))

    def _normalize_rms(self, audio: AudioBuffer, level: float, peak_limit: float) -> AudioBuffer:
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        rms = float(np.sqrt(np.mean(waveform ** 2)))
        target_rms = 10.0 ** (level / 20.0)

        if rms > 0:
            waveform = waveform * (target_rms / rms)

        waveform = np.clip(waveform, -peak_limit, peak_limit)

        return AudioBuffer(waveform, audio.sample_rate)

    def _normalize_peak(self, audio: AudioBuffer, level: float) -> AudioBuffer:
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        peak = float(np.abs(waveform).max()) if waveform.size > 0 else 0.0
        target_peak = 10.0 ** (level / 20.0)

        if peak > 0:
            waveform = waveform * (target_peak / peak)

        return AudioBuffer(waveform, audio.sample_rate)

    def _normalize_lufs(
        self,
        audio: AudioBuffer,
        level: float,
        tolerance: float,
        max_gain: float,
        true_peak_ceiling: float,
    ) -> AudioBuffer:
        from pedalboard import Pedalboard, Resample, Limiter
        import pyloudnorm as pyln
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        audio_2d = waveform[np.newaxis, :] if waveform.ndim == 1 else waveform
        meter_input = audio_2d[0] if audio_2d.shape[0] == 1 else audio_2d.T

        meter = pyln.Meter(audio.sample_rate)
        applied_gain_db = 0.0

        for _ in range(3):
            measured_loudness = meter.integrated_loudness(meter_input.astype(np.float64))

            if not np.isfinite(measured_loudness):
                break

            gain_needed_db = level - measured_loudness
            remaining_gain_db = max_gain - abs(applied_gain_db)

            if abs(gain_needed_db) <= tolerance or remaining_gain_db <= 0:
                break

            step = float(np.clip(gain_needed_db, -remaining_gain_db, remaining_gain_db))
            gain_linear = 10.0 ** (step / 20.0)
            audio_2d = audio_2d * gain_linear
            meter_input = audio_2d[0] if audio_2d.shape[0] == 1 else audio_2d.T
            applied_gain_db += step

        oversample = 4
        board = Pedalboard([
            Resample(target_sample_rate=audio.sample_rate * oversample, quality=Resample.Quality.WindowedSinc),
            Limiter(threshold_db=true_peak_ceiling, release_ms=100.0),
            Resample(target_sample_rate=audio.sample_rate, quality=Resample.Quality.WindowedSinc),
        ])
        processed = board(audio_2d.astype(np.float32), audio.sample_rate)

        return AudioBuffer(processed[0] if waveform.ndim == 1 else processed, audio.sample_rate)

    def _peak_limit_hard(self, audio: AudioBuffer, level: float) -> AudioBuffer:
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)

        if waveform.size > 0:
            peak = float(np.abs(waveform).max())

            if peak > level and peak > 0:
                waveform = waveform * (level / peak)

        return AudioBuffer(waveform, audio.sample_rate)

    def _peak_limit_smooth(self, audio: AudioBuffer, level: float, release_time: float) -> AudioBuffer:
        from pedalboard import Pedalboard, Limiter
        import numpy as np

        waveform = np.asarray(audio.waveform, dtype=np.float32)
        audio_2d = waveform if waveform.ndim == 2 else waveform[np.newaxis, :]

        board = Pedalboard([
            Limiter(threshold_db=level, release_ms=release_time * 1000.0),
        ])
        processed = board(audio_2d, audio.sample_rate)

        return AudioBuffer(processed[0] if waveform.ndim == 1 else processed, audio.sample_rate)

    def _apply_pitch_jitter(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        depth_semitones: float,
        rate_hz: float,
        rng: np.random.Generator,
        n_fft: int,
    ) -> np.ndarray:
        # Overlap-add segment-wise pitch shift with an LFO-driven semitone curve;
        # segment length matches the LFO period so the modulation is audible but
        # boundaries stay short enough to crossfade cleanly.
        import numpy as np
        import librosa

        n_samples = waveform.shape[-1]
        segment = max(int(sample_rate / max(rate_hz, 0.1)), n_fft)

        if n_samples <= segment:
            return waveform

        hop = segment // 2
        window = np.hanning(segment).astype(np.float32)
        accumulator = np.zeros(n_samples + segment, dtype=np.float32)
        norm = np.zeros_like(accumulator)

        step_index = 0
        for start in range(0, n_samples - segment + 1, hop):
            frame = waveform[start:start + segment]
            phase = 2.0 * np.pi * rate_hz * (start / sample_rate)
            lfo = np.sin(phase)
            noise = float(rng.standard_normal()) * 0.3
            semitones = depth_semitones * (lfo + noise)

            if abs(semitones) < 1e-3:
                shifted = frame
            else:
                shifted = librosa.effects.pitch_shift(
                    frame.astype(np.float32),
                    sr=sample_rate,
                    n_steps=float(semitones),
                )
                if shifted.size != segment:
                    shifted = np.resize(shifted, segment)

            accumulator[start:start + segment] += shifted * window
            norm[start:start + segment] += window
            step_index += 1

        mask = norm > 1e-6
        accumulator[mask] /= norm[mask]

        return accumulator[:n_samples]

    def _shift_formants(
        self,
        waveform: np.ndarray,
        ratio: float,
        n_fft: int,
        hop_length: int
    ) -> np.ndarray:
        # Warp the spectral envelope along the frequency axis while keeping the
        # residual (source) intact — approximates formant scaling.
        import numpy as np
        import librosa

        if waveform.shape[-1] < n_fft:
            return waveform

        stft = librosa.stft(waveform, n_fft=n_fft, hop_length=hop_length)
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        n_bins = magnitude.shape[0]
        smoothing = max(3, n_bins // 32)
        kernel = np.ones(smoothing, dtype=np.float32) / smoothing
        envelope = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), 0, magnitude)
        envelope = np.maximum(envelope, 1e-8)
        residual = magnitude / envelope

        src_bins = np.arange(n_bins, dtype=np.float32)
        query = src_bins / ratio
        warped_envelope = np.empty_like(envelope)

        for index in range(envelope.shape[1]):
            warped_envelope[:, index] = np.interp(query, src_bins, envelope[:, index], left=0.0, right=0.0)

        new_magnitude = warped_envelope * residual
        new_stft = new_magnitude * np.exp(1j * phase)

        return librosa.istft(new_stft, hop_length=hop_length, n_fft=n_fft, length=waveform.shape[-1]).astype(np.float32)

@register_audio_processor_service(AudioProcessorDriver.NATIVE)
class NativeAudioProcessorService(AudioProcessorService):
    def __init__(self, id: str, config: AudioProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pedalboard", "numpy", "torchaudio", "soxr", "pyloudnorm", "librosa" ]

    async def _run(self, action: AudioProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await NativeAudioProcessorAction(action).run(context)
