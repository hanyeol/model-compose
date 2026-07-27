from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import AudioEncoderParams
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class AudioExtractorAction(MediaComponentAction):
    def __init__(self, config: AudioExtractorActionConfig):
        self.config: AudioExtractorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source     = await context.render_media(self.config.source)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_sources, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_sources, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format   = await context.render_variable(self.config.format) if self.config.format else "mp3"
        encoding = await self._resolve_audio_encoder(context, self.config.encoding) if self.config.encoding else AudioEncoderParams()
        track    = await context.render_variable(self.config.track) if self.config.track is not None else None

        return {
            "format":   format,
            "encoding": encoding,
            "track":    int(track) if track is not None else None,
        }

    async def _process_batch(
        self,
        sources: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Optional[AudioStreamResource]]:
        results: List[Optional[AudioStreamResource]] = []
        for source in sources:
            results.append(await self._process(source, params, cancellation_token))
        return results

    async def _process(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Optional[AudioStreamResource]:
        if source is None:
            logging.debug("Audio extractor skipped because no source was provided.")
            return None

        return await self._extract(
            source,
            params["format"],
            params["encoding"],
            params["track"],
            cancellation_token,
        )

    @abstractmethod
    async def _extract(
        self,
        source: MediaSource,
        format: str,
        encoding: AudioEncoderParams,
        track: Optional[int],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        pass
