from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import FaceTrackingModelActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.atomic import AtomicList
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class FaceEmbedding(AtomicList):
    def __log__(self) -> str:
        return f"<FaceEmbedding dim={len(self)}>"

class FaceTrackingTaskAction(ComponentAction):
    def __init__(self, config: FaceTrackingModelActionConfig):
        self.config: FaceTrackingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        frames      = await context.render_image_array(self.config.frames)
        frame_rate  = await context.render_scalar(self.config.frame_rate, float)
        time_offset = await context.render_time(self.config.time_offset, 0.0)
        batch_size  = await context.render_variable(self.config.batch_size)

        if not frame_rate or frame_rate <= 0:
            raise ValueError(f"'frame_rate' must be > 0, got {frame_rate}")

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_frames, batch_offsets in BatchSourceIterator((frames, time_offset), batch_size=batch_size or 1):
                    batch_results = await self._track_batch(batch_frames, batch_offsets, frame_rate, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_frames, batch_offsets in BatchSourceIterator((frames, time_offset), batch_size=batch_size or 1):
                batch_results = await self._track_batch(batch_frames, batch_offsets, frame_rate, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        similarity_threshold     = await context.render_scalar(self.config.params.similarity_threshold, float)
        min_face_size            = await context.render_scalar(self.config.params.min_face_size, int)
        min_frame_count          = await context.render_scalar(self.config.params.min_frame_count, int)
        merge_gap                = await context.render_scalar(self.config.params.merge_gap, float)
        max_face_count_per_frame = await context.render_scalar(self.config.params.max_face_count_per_frame, int)
        return_image             = await context.render_scalar(self.config.return_image, bool)
        return_embedding         = await context.render_scalar(self.config.return_embedding, bool)
        bounding_box_padding     = await context.render_scalar(self.config.bounding_box_padding, float)

        if bounding_box_padding < 0.0:
            raise ValueError(f"'bounding_box_padding' must be >= 0.0, got {bounding_box_padding}")

        return {
            "similarity_threshold":     similarity_threshold,
            "min_face_size":            min_face_size,
            "min_frame_count":          min_frame_count,
            "merge_gap":                merge_gap,
            "max_face_count_per_frame": max_face_count_per_frame,
            "return_image":             return_image,
            "return_embedding":         return_embedding,
            "bounding_box_padding":     bounding_box_padding,
        }

    @abstractmethod
    async def _track_batch(
        self,
        frames_batch: List[ImageArrayValue],
        offsets_batch: List[float],
        frame_rate: float,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        """Run tracking on a batch of independent frame sequences. Each item in
        `frames_batch` is one video's ordered frames as an ImageArrayValue; the
        matching offset in `offsets_batch` is that video's timestamp for its
        first frame. Returns one tracking result dict per input video."""
        pass
