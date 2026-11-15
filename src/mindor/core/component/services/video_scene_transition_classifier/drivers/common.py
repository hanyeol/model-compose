from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoSceneTransitionClassifierActionConfig
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class VideoSceneTransitionClassifierAction(ComponentAction):
    """Driver-agnostic skeleton for video-scene-transition-classifier actions.

    Subclasses override `_resolve_params` and `_classify`; common.py only
    knows how to stream / batch each boundary-level classification.
    """
    def __init__(self, config: VideoSceneTransitionClassifierActionConfig):
        self.config: VideoSceneTransitionClassifierActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        scenes     = await context.render_array(self.config.scenes, single_as_array=True)
        frames     = await context.render_image_array(self.config.frames)
        frame_rate = await context.render_scalar(self.config.frame_rate, float) if self.config.frame_rate is not None else None
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_scalar(self.config.streaming, bool)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_frames in BatchSourceIterator(frames, batch_size=batch_size or 1):
                    batch_results = await self._classify_batch(scenes, batch_frames, frame_rate, streaming, params, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            context.register_source("result", result)
                            yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(frames, StreamChunkIterator) and frames.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_frames in BatchSourceIterator(frames, batch_size=batch_size or 1):
                batch_results = await self._classify_batch(scenes, batch_frames, frame_rate, streaming, params, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _classify_batch(
        self,
        scenes: Any,
        frames: List[ImageArrayValue],
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        scenes_batch = scenes if isinstance(scenes, list) else [ scenes ] * len(frames)

        results: List[Any] = []

        for index in range(len(frames)):
            results.append(await self._classify(scenes_batch[index], frames[index], frame_rate, streaming, params, cancellation_token))

        return results

    @abstractmethod
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _classify(
        self,
        scenes: ArrayValue,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        pass
