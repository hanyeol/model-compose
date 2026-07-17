from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioProcessorActionConfig, AudioProcessorActionMethod
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class AudioProcessorAction:
    def __init__(self, config: AudioProcessorActionConfig):
        self.config: AudioProcessorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_audios, self.config.method, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_audios, self.config.method, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: AudioProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == AudioProcessorActionMethod.HIGHPASS:
            cutoff = await context.render_variable(self.config.cutoff)

            return { "cutoff": float(cutoff) }

        if method == AudioProcessorActionMethod.LOWPASS:
            cutoff = await context.render_variable(self.config.cutoff)

            return { "cutoff": float(cutoff) }

        if method == AudioProcessorActionMethod.PITCH_SHIFT:
            semitones = await context.render_variable(self.config.semitones)

            return { "semitones": float(semitones) }

        if method == AudioProcessorActionMethod.DC_SHIFT:
            offset = await context.render_variable(self.config.offset) if self.config.offset is not None else None

            return { "offset": float(offset) if offset is not None else 0.0 }

        if method == AudioProcessorActionMethod.COMPRESSOR:
            threshold = await context.render_variable(self.config.threshold)
            ratio     = await context.render_variable(self.config.ratio)
            attack    = await context.render_variable(self.config.attack)
            release   = await context.render_variable(self.config.release)

            return {
                "threshold": float(threshold),
                "ratio":     float(ratio),
                "attack":    parse_time(attack),
                "release":   parse_time(release),
            }

        if method == AudioProcessorActionMethod.GAIN:
            level = await context.render_variable(self.config.level)

            return { "level": float(level) }

        if method == AudioProcessorActionMethod.CHORUS:
            rate     = await context.render_variable(self.config.rate)
            depth    = await context.render_variable(self.config.depth)
            feedback = await context.render_variable(self.config.feedback)
            delay    = await context.render_variable(self.config.delay)
            mix      = await context.render_variable(self.config.mix)

            return {
                "rate":     float(rate),
                "depth":    float(depth),
                "feedback": float(feedback),
                "delay":    parse_time(delay),
                "mix":      float(mix),
            }

        if method == AudioProcessorActionMethod.DELAY:
            time     = await context.render_variable(self.config.time)
            feedback = await context.render_variable(self.config.feedback)
            mix      = await context.render_variable(self.config.mix)

            return {
                "time":     parse_time(time),
                "feedback": float(feedback),
                "mix":      float(mix),
            }

        if method == AudioProcessorActionMethod.REVERB:
            room_size = await context.render_variable(self.config.room_size)
            damping   = await context.render_variable(self.config.damping)
            wet_level = await context.render_variable(self.config.wet_level)
            dry_level = await context.render_variable(self.config.dry_level)
            width     = await context.render_variable(self.config.width)

            return {
                "room_size": float(room_size),
                "damping":   float(damping),
                "wet_level": float(wet_level),
                "dry_level": float(dry_level),
                "width":     float(width),
            }

        if method == AudioProcessorActionMethod.NORMALIZE:
            level      = await context.render_variable(self.config.level)
            peak_limit = await context.render_variable(self.config.peak_limit)

            return {
                "level":      float(level),
                "peak_limit": float(peak_limit),
            }

        if method == AudioProcessorActionMethod.PEAK_LIMIT:
            level = await context.render_variable(self.config.level)

            return { "level": float(level) }

        if method == AudioProcessorActionMethod.TRIM_EDGES:
            threshold = await context.render_variable(self.config.threshold)
            padding   = await context.render_variable(self.config.padding) if self.config.padding is not None else None

            return {
                "threshold": float(threshold),
                "padding":   parse_time(padding) if padding is not None else 0.0,
            }

        if method == AudioProcessorActionMethod.TRIM_SILENCE:
            window               = await context.render_variable(self.config.window)
            threshold            = await context.render_variable(self.config.threshold)
            min_silence          = await context.render_variable(self.config.min_silence)
            max_internal_silence = await context.render_variable(self.config.max_internal_silence)
            fade                 = await context.render_variable(self.config.fade)

            return {
                "window":               parse_time(window),
                "threshold":            float(threshold),
                "min_silence":          parse_time(min_silence),
                "max_internal_silence": parse_time(max_internal_silence),
                "fade":                 parse_time(fade),
            }

        raise ValueError(f"Unsupported audio processor action method: {method}")

    async def _process_batch(
        self,
        audios: List[MediaSource],
        method: AudioProcessorActionMethod,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[PcmStreamResource]]:
        return await asyncio.gather(*[
            self._process(audio, method, params, loop) for audio in audios
        ])

    async def _process(
        self,
        audio: MediaSource,
        method: AudioProcessorActionMethod,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[PcmStreamResource]:
        if audio is None:
            logging.debug("Audio processor (%s) skipped because no audio was provided.", method)
            return None

        if method == AudioProcessorActionMethod.HIGHPASS:
            return await self._highpass(audio, params, loop)

        if method == AudioProcessorActionMethod.LOWPASS:
            return await self._lowpass(audio, params, loop)

        if method == AudioProcessorActionMethod.PITCH_SHIFT:
            return await self._pitch_shift(audio, params, loop)

        if method == AudioProcessorActionMethod.DC_SHIFT:
            return await self._dc_shift(audio, params, loop)

        if method == AudioProcessorActionMethod.COMPRESSOR:
            return await self._compressor(audio, params, loop)

        if method == AudioProcessorActionMethod.GAIN:
            return await self._gain(audio, params, loop)

        if method == AudioProcessorActionMethod.CHORUS:
            return await self._chorus(audio, params, loop)

        if method == AudioProcessorActionMethod.DELAY:
            return await self._delay(audio, params, loop)

        if method == AudioProcessorActionMethod.REVERB:
            return await self._reverb(audio, params, loop)

        if method == AudioProcessorActionMethod.NORMALIZE:
            return await self._normalize(audio, params, loop)

        if method == AudioProcessorActionMethod.PEAK_LIMIT:
            return await self._peak_limit(audio, params, loop)

        if method == AudioProcessorActionMethod.TRIM_EDGES:
            return await self._trim_edges(audio, params, loop)

        if method == AudioProcessorActionMethod.TRIM_SILENCE:
            return await self._trim_silence(audio, params, loop)

        raise ValueError(f"Unsupported audio processor action method: {method}")

    @abstractmethod
    async def _highpass(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _lowpass(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _pitch_shift(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _dc_shift(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _compressor(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _gain(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _chorus(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _delay(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _reverb(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _normalize(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _peak_limit(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _trim_edges(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass

    @abstractmethod
    async def _trim_silence(self, audio: MediaSource, params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> PcmStreamResource:
        pass
