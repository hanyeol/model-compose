from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.foundation.media.encoding import AudioEncoderParams
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ....action.media import VideoAudioEncodingResolver
from ..base import ComponentActionContext

class AudioExtractorAction(ComponentAction):
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
                    batch_results = await self._extract_batch(batch_sources, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._extract_batch(batch_sources, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format   = await context.render_scalar(self.config.format, str, "mp3")
        encoding = await VideoAudioEncodingResolver.resolve_audio(context, self.config.encoding) if self.config.encoding else AudioEncoderParams()
        track    = await context.render_scalar(self.config.track, int)

        return {
            "format":   format,
            "encoding": encoding,
            "track":    track,
        }

    @abstractmethod
    async def _extract_batch(
        self,
        sources: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AudioStreamResource]:
        pass
