from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.streaming.audio import AudioStreamResource
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, AsyncIterator):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_audios, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_audios, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format      = await context.render_variable(self.config.format) if self.config.format else "wav"
        codec       = await context.render_variable(self.config.codec) if self.config.codec else None
        bitrate     = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        sample_rate = await context.render_variable(self.config.sample_rate) if self.config.sample_rate is not None else None
        channels    = await context.render_variable(self.config.channels) if self.config.channels is not None else None

        return {
            "format":      format,
            "codec":       codec,
            "bitrate":     bitrate,
            "sample_rate": sample_rate,
            "channels":    channels,
        }

    async def _process_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[AudioStreamResource]]:
        return await asyncio.gather(*[
            self._process(audio, params, loop) for audio in audios
        ])

    async def _process(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[AudioStreamResource]:
        if audio is None:
            logging.debug("Audio converter skipped because no audio was provided.")
            return None

        return await self._convert(
            audio,
            params["format"],
            params["codec"],
            params["bitrate"],
            params["sample_rate"],
            params["channels"],
            loop,
        )

    @abstractmethod
    async def _convert(
        self,
        source: MediaSource,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        sample_rate: Optional[Any],
        channels: Optional[Any],
        loop: asyncio.AbstractEventLoop,
    ) -> AudioStreamResource:
        pass
