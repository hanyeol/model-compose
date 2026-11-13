from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoTextScoringModelActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

class VideoTextScore(AtomicDict):
    def __log__(self) -> str:
        cosine = self.get("cosine")
        if isinstance(cosine, list):
            return f"<VideoTextScore pairs={len(cosine)}>"
        return f"<VideoTextScore cosine={cosine:.4f}>"

class VideoTextScoringTaskAction(ModelTaskComponentAction):
    def __init__(self, config: VideoTextScoringModelActionConfig):
        self.config: VideoTextScoringModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        frames     = await context.render_image_array(self.config.frames, single_as_array=True)
        text       = await context.render_text_array(self.config.text, single_as_array=True)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        # Wrap collect-mode input in an ArrayValue so BatchSourceIterator sees it
        # as a scalar — N videos × K texts stay bundled in one X-CLIP forward.
        if not isinstance(frames, (StreamIterator, AsyncIterator)):
            frames = ArrayValue([ frames ] if is_single_input else frames)

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_frames, batch_texts in BatchSourceIterator((frames, text), batch_size=batch_size or 1):
                    batch_scores = await self._score_batch(batch_frames, batch_texts, params, context.cancellation_token)
                    for score in batch_scores:
                        result = VideoTextScore(score)
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(frames, StreamChunkIterator) and frames.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[VideoTextScore] = []
            async for batch_frames, batch_texts in BatchSourceIterator((frames, text), batch_size=batch_size or 1):
                batch_scores = await self._score_batch(batch_frames, batch_texts, params, context.cancellation_token)
                results.extend(VideoTextScore(score) for score in batch_scores)

            result = results[0]  # collect-mode packs every video into one job
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return_logit   = await context.render_variable(self.config.params.return_logit)
        return_softmax = await context.render_variable(self.config.params.return_softmax)

        return {
            "return_logit":   return_logit,
            "return_softmax": return_softmax,
        }

    @abstractmethod
    async def _score_batch(
        self,
        frames: List[Union[ArrayValue, ImageArrayValue]],
        texts: List[TextArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
