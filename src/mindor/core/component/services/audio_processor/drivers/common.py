from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioProcessorActionConfig, AudioProcessorActionMethod, AudioProcessorNormalizeMode, AudioProcessorPeakLimitMode
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.streaming.audio import PcmStreamResource, AudioBufferStreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
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

        is_fragmented    = isinstance(audio, StreamChunkIterator) and audio.is_fragmented
        is_single_input  = is_fragmented or not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)) and not is_fragmented:
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_audios, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Optional[PcmStreamResource]] = []
            async for batch_audios in BatchSourceIterator([ audio ] if is_fragmented else audio, batch_size=batch_size or 1):
                batch_results = await self._process_batch(self.config.method, batch_audios, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        return await context.render_audio_buffer(self.config.audio, collect=False)

    async def _resolve_params(self, method: AudioProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == AudioProcessorActionMethod.RESAMPLE:
            sample_rate = await context.render_scalar(self.config.sample_rate, int)

            return { "sample_rate": sample_rate }

        if method == AudioProcessorActionMethod.HIGHPASS:
            cutoff = await context.render_scalar(self.config.cutoff, float)

            return { "cutoff": cutoff }

        if method == AudioProcessorActionMethod.LOWPASS:
            cutoff = await context.render_scalar(self.config.cutoff, float)

            return { "cutoff": cutoff }

        if method == AudioProcessorActionMethod.BELL:
            frequency = await context.render_scalar(self.config.frequency, float)
            gain      = await context.render_scalar(self.config.gain, float)
            q         = await context.render_scalar(self.config.q, float)

            return {
                "frequency": frequency,
                "gain":      gain,
                "q":         q,
            }

        if method == AudioProcessorActionMethod.LOW_SHELF:
            frequency = await context.render_scalar(self.config.frequency, float)
            gain      = await context.render_scalar(self.config.gain, float)
            q         = await context.render_scalar(self.config.q, float)

            return {
                "frequency": frequency,
                "gain":      gain,
                "q":         q,
            }

        if method == AudioProcessorActionMethod.HIGH_SHELF:
            frequency = await context.render_scalar(self.config.frequency, float)
            gain      = await context.render_scalar(self.config.gain, float)
            q         = await context.render_scalar(self.config.q, float)

            return {
                "frequency": frequency,
                "gain":      gain,
                "q":         q,
            }

        if method == AudioProcessorActionMethod.PITCH_SHIFT:
            semitones = await context.render_scalar(self.config.semitones, float)

            return { "semitones": semitones }

        if method == AudioProcessorActionMethod.DC_SHIFT:
            offset = await context.render_scalar(self.config.offset, float, 0.0)

            return { "offset": offset }

        if method == AudioProcessorActionMethod.COMPRESSOR:
            threshold    = await context.render_scalar(self.config.threshold, float)
            ratio        = await context.render_scalar(self.config.ratio, float)
            attack_time  = await context.render_scalar(self.config.attack_time, "time")
            release_time = await context.render_scalar(self.config.release_time, "time")

            return {
                "threshold":    threshold,
                "ratio":        ratio,
                "attack_time":  attack_time,
                "release_time": release_time,
            }

        if method == AudioProcessorActionMethod.NOISE_GATE:
            threshold    = await context.render_scalar(self.config.threshold, float)
            ratio        = await context.render_scalar(self.config.ratio, float)
            attack_time  = await context.render_scalar(self.config.attack_time, "time")
            release_time = await context.render_scalar(self.config.release_time, "time")

            return {
                "threshold":    threshold,
                "ratio":        ratio,
                "attack_time":  attack_time,
                "release_time": release_time,
            }

        if method == AudioProcessorActionMethod.DISTORTION:
            drive = await context.render_scalar(self.config.drive, float)

            return { "drive": drive }

        if method == AudioProcessorActionMethod.SATURATION:
            drive = await context.render_scalar(self.config.drive, float)

            return { "drive": drive }

        if method == AudioProcessorActionMethod.GAIN:
            level = await context.render_scalar(self.config.level, float)

            return { "level": level }

        if method == AudioProcessorActionMethod.CHORUS:
            rate     = await context.render_scalar(self.config.rate, float)
            depth    = await context.render_scalar(self.config.depth, float)
            feedback = await context.render_scalar(self.config.feedback, float)
            delay    = await context.render_scalar(self.config.delay, "time")
            mix      = await context.render_scalar(self.config.mix, float)

            return {
                "rate":     rate,
                "depth":    depth,
                "feedback": feedback,
                "delay":    delay,
                "mix":      mix,
            }

        if method == AudioProcessorActionMethod.DELAY:
            time     = await context.render_scalar(self.config.time, "time")
            feedback = await context.render_scalar(self.config.feedback, float)
            mix      = await context.render_scalar(self.config.mix, float)

            return {
                "time":     time,
                "feedback": feedback,
                "mix":      mix,
            }

        if method == AudioProcessorActionMethod.REVERB:
            room_size = await context.render_scalar(self.config.room_size, float)
            damping   = await context.render_scalar(self.config.damping, float)
            wet_level = await context.render_scalar(self.config.wet_level, float)
            dry_level = await context.render_scalar(self.config.dry_level, float)
            width     = await context.render_scalar(self.config.width, float)

            return {
                "room_size": room_size,
                "damping":   damping,
                "wet_level": wet_level,
                "dry_level": dry_level,
                "width":     width,
            }

        if method == AudioProcessorActionMethod.NORMALIZE:
            if self.config.mode == AudioProcessorNormalizeMode.RMS:
                level      = await context.render_scalar(self.config.level, float)
                peak_limit = await context.render_scalar(self.config.peak_limit, float)

                return {
                    "mode":       AudioProcessorNormalizeMode.RMS,
                    "level":      level,
                    "peak_limit": peak_limit,
                }

            if self.config.mode == AudioProcessorNormalizeMode.PEAK:
                level = await context.render_scalar(self.config.level, float)

                return {
                    "mode":  AudioProcessorNormalizeMode.PEAK,
                    "level": level,
                }

            if self.config.mode == AudioProcessorNormalizeMode.LUFS:
                level             = await context.render_scalar(self.config.level, float)
                tolerance         = await context.render_scalar(self.config.tolerance, float)
                max_gain          = await context.render_scalar(self.config.max_gain, float)
                true_peak_ceiling = await context.render_scalar(self.config.true_peak_ceiling, float)

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
                level = await context.render_scalar(self.config.level, float)

                return {
                    "mode":  AudioProcessorPeakLimitMode.HARD,
                    "level": level,
                }

            if self.config.mode == AudioProcessorPeakLimitMode.SMOOTH:
                level        = await context.render_scalar(self.config.level, float)
                release_time = await context.render_scalar(self.config.release_time, "time")

                return {
                    "mode":         AudioProcessorPeakLimitMode.SMOOTH,
                    "level":        level,
                    "release_time": release_time,
                }

            raise ValueError(f"Unsupported peak-limit mode: {self.config.mode}")

        if method == AudioProcessorActionMethod.TRIM_EDGES:
            threshold = await context.render_scalar(self.config.threshold, float)
            padding   = await context.render_scalar(self.config.padding, "time", 0.0)

            return {
                "threshold": threshold,
                "padding":   padding,
            }

        if method == AudioProcessorActionMethod.TRIM_SILENCE:
            window               = await context.render_scalar(self.config.window, "time")
            threshold            = await context.render_scalar(self.config.threshold, float)
            min_silence          = await context.render_scalar(self.config.min_silence, "time")
            max_internal_silence = await context.render_scalar(self.config.max_internal_silence, "time")
            fade                 = await context.render_scalar(self.config.fade, "time")

            return {
                "window":               window,
                "threshold":            threshold,
                "min_silence":          min_silence,
                "max_internal_silence": max_internal_silence,
                "fade":                 fade,
            }

        if method == AudioProcessorActionMethod.FADE_IN:
            duration = await context.render_scalar(self.config.duration, "time")

            return { "duration": duration }

        if method == AudioProcessorActionMethod.FADE_OUT:
            duration = await context.render_scalar(self.config.duration, "time")

            return { "duration": duration }

        raise ValueError(f"Unsupported audio processor action method: {method}")

    async def _process_batch(
        self,
        method: AudioProcessorActionMethod,
        audios: List[Optional[AudioBufferStreamIterator]],
        params: Dict[str, Any],
    ) -> List[Optional[PcmStreamResource]]:
        return await asyncio.gather(*[
            self._process(method, audio, params) for audio in audios
        ])

    async def _process(
        self,
        method: AudioProcessorActionMethod,
        audio: Optional[AudioBufferStreamIterator],
        params: Dict[str, Any],
    ) -> Optional[PcmStreamResource]:
        if audio is None:
            logging.debug("Audio processor (%s) skipped because no audio was provided.", method)
            return None

        if method == AudioProcessorActionMethod.RESAMPLE:
            return PcmStreamResource(await self._resample(audio, params))

        if method == AudioProcessorActionMethod.HIGHPASS:
            return PcmStreamResource(await self._highpass(audio, params))

        if method == AudioProcessorActionMethod.LOWPASS:
            return PcmStreamResource(await self._lowpass(audio, params))

        if method == AudioProcessorActionMethod.BELL:
            return PcmStreamResource(await self._bell(audio, params))

        if method == AudioProcessorActionMethod.LOW_SHELF:
            return PcmStreamResource(await self._low_shelf(audio, params))

        if method == AudioProcessorActionMethod.HIGH_SHELF:
            return PcmStreamResource(await self._high_shelf(audio, params))

        if method == AudioProcessorActionMethod.PITCH_SHIFT:
            return PcmStreamResource(await self._pitch_shift(audio, params))

        if method == AudioProcessorActionMethod.DC_SHIFT:
            return PcmStreamResource(await self._dc_shift(audio, params))

        if method == AudioProcessorActionMethod.COMPRESSOR:
            return PcmStreamResource(await self._compressor(audio, params))

        if method == AudioProcessorActionMethod.NOISE_GATE:
            return PcmStreamResource(await self._noise_gate(audio, params))

        if method == AudioProcessorActionMethod.DISTORTION:
            return PcmStreamResource(await self._distortion(audio, params))

        if method == AudioProcessorActionMethod.SATURATION:
            return PcmStreamResource(await self._saturation(audio, params))

        if method == AudioProcessorActionMethod.GAIN:
            return PcmStreamResource(await self._gain(audio, params))

        if method == AudioProcessorActionMethod.CHORUS:
            return PcmStreamResource(await self._chorus(audio, params))

        if method == AudioProcessorActionMethod.DELAY:
            return PcmStreamResource(await self._delay(audio, params))

        if method == AudioProcessorActionMethod.REVERB:
            return PcmStreamResource(await self._reverb(audio, params))

        if method == AudioProcessorActionMethod.NORMALIZE:
            return PcmStreamResource(await self._normalize(audio, params))

        if method == AudioProcessorActionMethod.PEAK_LIMIT:
            return PcmStreamResource(await self._peak_limit(audio, params))

        if method == AudioProcessorActionMethod.TRIM_EDGES:
            return PcmStreamResource(await self._trim_edges(audio, params))

        if method == AudioProcessorActionMethod.TRIM_SILENCE:
            return PcmStreamResource(await self._trim_silence(audio, params))

        if method == AudioProcessorActionMethod.FADE_IN:
            return PcmStreamResource(await self._fade_in(audio, params))

        if method == AudioProcessorActionMethod.FADE_OUT:
            return PcmStreamResource(await self._fade_out(audio, params))

        raise ValueError(f"Unsupported audio processor action method: {method}")

    @abstractmethod
    async def _resample(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _highpass(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _lowpass(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _bell(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _low_shelf(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _high_shelf(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _pitch_shift(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _dc_shift(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _compressor(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _noise_gate(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _distortion(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _saturation(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _gain(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _chorus(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _delay(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _reverb(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _normalize(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _peak_limit(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _trim_edges(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _trim_silence(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _fade_in(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass

    @abstractmethod
    async def _fade_out(self, audio: AudioBufferStreamIterator, params: Dict[str, Any]) -> AudioBufferStreamIterator:
        pass
