from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.utils.iterators import AsyncSourceIterator
from mindor.core.utils.audio import AudioStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class AudioExtractorAction:
    def __init__(self, config: AudioExtractorActionConfig):
        self.config: AudioExtractorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source     = await context.render_media(self.config.source)
        batch_size = await context.render_variable(self.config.batch_size)

        is_stream_input  = isinstance(source, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or is_stream_input

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_sources in AsyncSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_sources, context)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()

        is_single_input: bool = not isinstance(source, (list, AsyncIterator))
        results = []
        async for batch_sources in AsyncSourceIterator(source, batch_size=batch_size or 1):
            batch_results = await self._process_batch(batch_sources, context)
            results.extend(batch_results)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(self, sources: List[MediaSource], context: ComponentActionContext) -> List[Optional[AudioStreamResource]]:
        params = await self._resolve_params(context)

        return await asyncio.gather(*[
            self._process(source, params) for source in sources
        ])

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format  = await context.render_variable(self.config.format) if self.config.format else "mp3"
        codec   = await context.render_variable(self.config.codec) if self.config.codec else None
        bitrate = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        track   = await context.render_variable(self.config.track) if self.config.track is not None else None

        if track is not None:
            track = int(track)

        return {
            "format":  format,
            "codec":   codec,
            "bitrate": bitrate,
            "track":   track,
        }

    async def _process(self, source: MediaSource, params: Dict[str, Any]) -> Optional[AudioStreamResource]:
        if source is None:
            logging.debug("Audio extractor skipped because no source was provided.")
            return None

        return await self._extract(
            source,
            params["format"],
            params["codec"],
            params["bitrate"],
            params["track"],
        )

    @abstractmethod
    async def _extract(
        self,
        source: MediaSource,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        track: Optional[int],
    ) -> AudioStreamResource:
        pass
