from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoMotionEstimatorActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

if TYPE_CHECKING:
    from PIL import Image as PILImage

class VideoMotionEstimatorAction(ComponentAction):
    config: VideoMotionEstimatorActionConfig

    """Driver-agnostic skeleton for video-motion-estimator actions.

    Subclasses declare their own mode set and override `_resolve_params`
    and `_estimate` to dispatch on that set — common.py does not know which
    modes exist, only how to stream/batch them.
    """
    async def run(self, context: ComponentActionContext) -> Any:
        frames     = await context.render_image_array(self.config.frames)
        frame_rate = await context.render_scalar(self.config.frame_rate, float) if self.config.frame_rate is not None else None
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_scalar(self.config.streaming, bool)

        params = await self._resolve_params(self.config.mode, context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_frames in BatchSourceIterator(frames, batch_size=batch_size or 1):
                    batch_results = await self._estimate_batch(batch_frames, self.config.mode, frame_rate, streaming, params, context.cancellation_token)
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
                batch_results = await self._estimate_batch(batch_frames, self.config.mode, frame_rate, streaming, params, context.cancellation_token)
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

    async def _estimate_batch(
        self,
        frames: List[ImageArrayValue],
        mode: Any,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        results: List[Any] = []

        for index in range(len(frames)):
            results.append(await self._estimate(mode, frames[index], frame_rate, streaming, params, cancellation_token))

        return results

    @abstractmethod
    async def _resolve_params(self, mode: Any, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _estimate(
        self,
        mode: Any,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        pass
