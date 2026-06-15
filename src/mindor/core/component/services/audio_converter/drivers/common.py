from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.utils.iterators import AsyncSourceIterator
from mindor.core.utils.audio import AudioStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        is_stream_input  = isinstance(audio, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or is_stream_input

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_audios in AsyncSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_audios, context)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()

        is_single_input: bool = not isinstance(audio, (list, AsyncIterator))
        results = []
        async for batch_audios in AsyncSourceIterator(audio, batch_size=batch_size or 1):
            batch_results = await self._process_batch(batch_audios, context)
            results.extend(batch_results)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(self, audios: List[MediaSource], context: ComponentActionContext) -> List[Optional[AudioStreamResource]]:
        params = await self._resolve_params(context)

        return await asyncio.gather(*[
            self._process(audio, params) for audio in audios
        ])

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

    async def _process(self, audio: MediaSource, params: Dict[str, Any]) -> Optional[AudioStreamResource]:
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
    ) -> AudioStreamResource:
        pass
