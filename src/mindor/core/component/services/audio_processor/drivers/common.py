from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioProcessorActionConfig, AudioProcessorActionMethod, AudioProcessorNormalizeMode, AudioProcessorPeakLimitMode
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.audio import encode_waveform_to_pcm, AudioBuffer
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from ..base import ComponentActionContext
from ....action.base import ComponentAction
import asyncio

class AudioProcessorAction(ComponentAction):
    def __init__(self, config: AudioProcessorActionConfig):
        self.config: AudioProcessorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_audios, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Optional[PcmStreamResource]] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._process_batch(self.config.method, batch_audios, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        return await context.render_audio_buffer(self.config.audio)

    async def _resolve_params(self, method: AudioProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == AudioProcessorActionMethod.RESAMPLE:
            sample_rate = int(await context.render_variable(self.config.sample_rate))

            return { "sample_rate": sample_rate }

        if method == AudioProcessorActionMethod.HIGHPASS:
            cutoff = float(await context.render_variable(self.config.cutoff))

            return { "cutoff": cutoff }

        if method == AudioProcessorActionMethod.LOWPASS:
            cutoff = float(await context.render_variable(self.config.cutoff))

            return { "cutoff": cutoff }

        if method == AudioProcessorActionMethod.BELL:
            frequency = float(await context.render_variable(self.config.frequency))
            gain      = float(await context.render_variable(self.config.gain))
            q         = float(await context.render_variable(self.config.q))

            return {
                "frequency": frequency,
                "gain":      gain,
                "q":         q,
            }

        if method == AudioProcessorActionMethod.LOW_SHELF:
            frequency = float(await context.render_variable(self.config.frequency))
            gain      = float(await context.render_variable(self.config.gain))
            q         = float(await context.render_variable(self.config.q))

            return {
                "frequency": frequency,
                "gain":      gain,
                "q":         q,
            }

        if method == AudioProcessorActionMethod.HIGH_SHELF:
            frequency = float(await context.render_variable(self.config.frequency))
            gain      = float(await context.render_variable(self.config.gain))
            q         = float(await context.render_variable(self.config.q))

            return {
                "frequency": frequency,
                "gain":      gain,
                "q":         q,
            }

        if method == AudioProcessorActionMethod.PITCH_SHIFT:
            semitones = float(await context.render_variable(self.config.semitones))

            return { "semitones": semitones }

        if method == AudioProcessorActionMethod.DC_SHIFT:
            offset = float(await context.render_variable(self.config.offset)) if self.config.offset is not None else 0.0

            return { "offset": offset }

        if method == AudioProcessorActionMethod.COMPRESSOR:
            threshold = float(await context.render_variable(self.config.threshold))
            ratio     = float(await context.render_variable(self.config.ratio))
            attack    = parse_time(await context.render_variable(self.config.attack))
            release   = parse_time(await context.render_variable(self.config.release))

            return {
                "threshold": threshold,
                "ratio":     ratio,
                "attack":    attack,
                "release":   release,
            }

        if method == AudioProcessorActionMethod.NOISE_GATE:
            threshold = float(await context.render_variable(self.config.threshold))
            ratio     = float(await context.render_variable(self.config.ratio))
            attack    = parse_time(await context.render_variable(self.config.attack))
            release   = parse_time(await context.render_variable(self.config.release))

            return {
                "threshold": threshold,
                "ratio":     ratio,
                "attack":    attack,
                "release":   release,
            }

        if method == AudioProcessorActionMethod.DISTORTION:
            drive = float(await context.render_variable(self.config.drive))

            return { "drive": drive }

        if method == AudioProcessorActionMethod.SATURATION:
            drive = float(await context.render_variable(self.config.drive))

            return { "drive": drive }

        if method == AudioProcessorActionMethod.GAIN:
            level = float(await context.render_variable(self.config.level))

            return { "level": level }

        if method == AudioProcessorActionMethod.CHORUS:
            rate     = float(await context.render_variable(self.config.rate))
            depth    = float(await context.render_variable(self.config.depth))
            feedback = float(await context.render_variable(self.config.feedback))
            delay    = parse_time(await context.render_variable(self.config.delay))
            mix      = float(await context.render_variable(self.config.mix))

            return {
                "rate":     rate,
                "depth":    depth,
                "feedback": feedback,
                "delay":    delay,
                "mix":      mix,
            }

        if method == AudioProcessorActionMethod.DELAY:
            time     = parse_time(await context.render_variable(self.config.time))
            feedback = float(await context.render_variable(self.config.feedback))
            mix      = float(await context.render_variable(self.config.mix))

            return {
                "time":     time,
                "feedback": feedback,
                "mix":      mix,
            }

        if method == AudioProcessorActionMethod.REVERB:
            room_size = float(await context.render_variable(self.config.room_size))
            damping   = float(await context.render_variable(self.config.damping))
            wet_level = float(await context.render_variable(self.config.wet_level))
            dry_level = float(await context.render_variable(self.config.dry_level))
            width     = float(await context.render_variable(self.config.width))

            return {
                "room_size": room_size,
                "damping":   damping,
                "wet_level": wet_level,
                "dry_level": dry_level,
                "width":     width,
            }

        if method == AudioProcessorActionMethod.NORMALIZE:
            if self.config.mode == AudioProcessorNormalizeMode.RMS:
                level      = float(await context.render_variable(self.config.level))
                peak_limit = float(await context.render_variable(self.config.peak_limit))

                return {
                    "mode":       AudioProcessorNormalizeMode.RMS,
                    "level":      level,
                    "peak_limit": peak_limit,
                }

            if self.config.mode == AudioProcessorNormalizeMode.PEAK:
                level = float(await context.render_variable(self.config.level))

                return {
                    "mode":  AudioProcessorNormalizeMode.PEAK,
                    "level": level,
                }

            if self.config.mode == AudioProcessorNormalizeMode.LUFS:
                level             = float(await context.render_variable(self.config.level))
                tolerance         = float(await context.render_variable(self.config.tolerance))
                max_gain          = float(await context.render_variable(self.config.max_gain))
                true_peak_ceiling = float(await context.render_variable(self.config.true_peak_ceiling))

                return {
                    "mode":              AudioProcessorNormalizeMode.LUFS,
                    "level":             level,
                    "tolerance":         tolerance,
                    "max_gain":          max_gain,
                    "true_peak_ceiling": true_peak_ceiling,
                }

            raise ValueError(f"Unsupported normalize mode: {self.config.mode}")

        if method == AudioProcessorActionMethod.PEAK_LIMIT:
            if self.config.mode == AudioProcessorPeakLimitMode.HARD:
                level = float(await context.render_variable(self.config.level))

                return {
                    "mode":  AudioProcessorPeakLimitMode.HARD,
                    "level": level,
                }

            if self.config.mode == AudioProcessorPeakLimitMode.SMOOTH:
                level   = float(await context.render_variable(self.config.level))
                release = parse_time(await context.render_variable(self.config.release))

                return {
                    "mode":    AudioProcessorPeakLimitMode.SMOOTH,
                    "level":   level,
                    "release": release,
                }

            raise ValueError(f"Unsupported peak-limit mode: {self.config.mode}")

        if method == AudioProcessorActionMethod.TRIM_EDGES:
            threshold = float(await context.render_variable(self.config.threshold))
            padding   = parse_time(await context.render_variable(self.config.padding)) if self.config.padding is not None else 0.0

            return {
                "threshold": threshold,
                "padding":   padding,
            }

        if method == AudioProcessorActionMethod.TRIM_SILENCE:
            window               = parse_time(await context.render_variable(self.config.window))
            threshold            = float(await context.render_variable(self.config.threshold))
            min_silence          = parse_time(await context.render_variable(self.config.min_silence))
            max_internal_silence = parse_time(await context.render_variable(self.config.max_internal_silence))
            fade                 = parse_time(await context.render_variable(self.config.fade))

            return {
                "window":               window,
                "threshold":            threshold,
                "min_silence":          min_silence,
                "max_internal_silence": max_internal_silence,
                "fade":                 fade,
            }

        if method == AudioProcessorActionMethod.FADE_IN:
            duration = parse_time(await context.render_variable(self.config.duration))

            return { "duration": duration }

        if method == AudioProcessorActionMethod.FADE_OUT:
            duration = parse_time(await context.render_variable(self.config.duration))

            return { "duration": duration }

        raise ValueError(f"Unsupported audio processor action method: {method}")

    async def _process_batch(
        self,
        method: AudioProcessorActionMethod,
        audios: List[Optional[AudioBuffer]],
        params: Dict[str, Any],
    ) -> List[Optional[PcmStreamResource]]:
        return await asyncio.gather(*[
            self._process(method, audio, params) for audio in audios
        ])

    async def _process(
        self,
        method: AudioProcessorActionMethod,
        audio: Optional[AudioBuffer],
        params: Dict[str, Any],
    ) -> Optional[PcmStreamResource]:
        if audio is None:
            logging.debug("Audio processor (%s) skipped because no audio was provided.", method)
            return None

        if method == AudioProcessorActionMethod.RESAMPLE:
            audio = await self._resample(audio, params)
        elif method == AudioProcessorActionMethod.HIGHPASS:
            audio = await self._highpass(audio, params)
        elif method == AudioProcessorActionMethod.LOWPASS:
            audio = await self._lowpass(audio, params)
        elif method == AudioProcessorActionMethod.BELL:
            audio = await self._bell(audio, params)
        elif method == AudioProcessorActionMethod.LOW_SHELF:
            audio = await self._low_shelf(audio, params)
        elif method == AudioProcessorActionMethod.HIGH_SHELF:
            audio = await self._high_shelf(audio, params)
        elif method == AudioProcessorActionMethod.PITCH_SHIFT:
            audio = await self._pitch_shift(audio, params)
        elif method == AudioProcessorActionMethod.DC_SHIFT:
            audio = await self._dc_shift(audio, params)
        elif method == AudioProcessorActionMethod.COMPRESSOR:
            audio = await self._compressor(audio, params)
        elif method == AudioProcessorActionMethod.NOISE_GATE:
            audio = await self._noise_gate(audio, params)
        elif method == AudioProcessorActionMethod.DISTORTION:
            audio = await self._distortion(audio, params)
        elif method == AudioProcessorActionMethod.SATURATION:
            audio = await self._saturation(audio, params)
        elif method == AudioProcessorActionMethod.GAIN:
            audio = await self._gain(audio, params)
        elif method == AudioProcessorActionMethod.CHORUS:
            audio = await self._chorus(audio, params)
        elif method == AudioProcessorActionMethod.DELAY:
            audio = await self._delay(audio, params)
        elif method == AudioProcessorActionMethod.REVERB:
            audio = await self._reverb(audio, params)
        elif method == AudioProcessorActionMethod.NORMALIZE:
            audio = await self._normalize(audio, params)
        elif method == AudioProcessorActionMethod.PEAK_LIMIT:
            audio = await self._peak_limit(audio, params)
        elif method == AudioProcessorActionMethod.TRIM_EDGES:
            audio = await self._trim_edges(audio, params)
        elif method == AudioProcessorActionMethod.TRIM_SILENCE:
            audio = await self._trim_silence(audio, params)
        elif method == AudioProcessorActionMethod.FADE_IN:
            audio = await self._fade_in(audio, params)
        elif method == AudioProcessorActionMethod.FADE_OUT:
            audio = await self._fade_out(audio, params)
        else:
            raise ValueError(f"Unsupported audio processor action method: {method}")

        return self._encode(audio)

    def _encode(self, audio: AudioBuffer) -> PcmStreamResource:
        samples, channels = encode_waveform_to_pcm(audio.waveform)

        return PcmStreamResource(samples, {
            "sample_rate": str(int(audio.sample_rate)),
            "channels":    str(channels),
            "bit_depth":   "16",
        })

    @abstractmethod
    async def _resample(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _highpass(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _lowpass(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _bell(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _low_shelf(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _high_shelf(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _pitch_shift(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _dc_shift(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _compressor(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _noise_gate(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _distortion(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _saturation(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _gain(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _chorus(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _delay(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _reverb(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _normalize(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _peak_limit(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _trim_edges(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _trim_silence(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _fade_in(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass

    @abstractmethod
    async def _fade_out(self, audio: AudioBuffer, params: Dict[str, Any]) -> AudioBuffer:
        pass
