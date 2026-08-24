from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.foundation.media.encoding import AudioEncoderParams
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction
from ....action.media import VideoAudioEncodingResolver

class AudioConverterAction(ComponentAction):
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._convert_batch(batch_audios, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._convert_batch(batch_audios, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format   = await context.render_scalar(self.config.format, str, "wav")
        encoding = await VideoAudioEncodingResolver.resolve_audio(context, self.config.encoding) if self.config.encoding else AudioEncoderParams()

        return {
            "format":   format,
            "encoding": encoding,
        }

    @abstractmethod
    async def _convert_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AudioStreamResource]:
        pass
