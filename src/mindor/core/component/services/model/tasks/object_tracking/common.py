from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterable, AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ObjectTrackingModelActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class ObjectTrackingTaskAction(ComponentAction):
    def __init__(self, config: ObjectTrackingModelActionConfig):
        self.config: ObjectTrackingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        frames      = await context.render_image_array(self.config.frames)
        frame_rate  = await context.render_scalar(self.config.frame_rate, float)
        time_offset = await context.render_time(self.config.time_offset, 0.0)
        batch_size  = await context.render_variable(self.config.batch_size)
        streaming   = await context.render_scalar(self.config.streaming, bool)

        if not frame_rate or frame_rate <= 0:
            raise ValueError(f"'frame_rate' must be > 0, got {frame_rate}")

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_frames, batch_offsets in BatchSourceIterator((frames, time_offset), batch_size=batch_size or 1):
                    batch_results = await self._track_batch(batch_frames, batch_offsets, frame_rate, streaming, params, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_frames, batch_offsets in BatchSourceIterator((frames, time_offset), batch_size=batch_size or 1):
                batch_results = await self._track_batch(batch_frames, batch_offsets, frame_rate, streaming, params, context.cancellation_token)
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

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        labels                     = await context.render_variable(self.config.labels)
        min_confidence             = await context.render_scalar(self.config.params.min_confidence, float)
        iou_threshold              = await context.render_scalar(self.config.params.iou_threshold, float)
        agnostic_nms               = await context.render_scalar(self.config.params.agnostic_nms, bool)
        min_object_size            = await context.render_scalar(self.config.params.min_object_size, int)
        min_frame_count            = await context.render_scalar(self.config.params.min_frame_count, int)
        max_object_count_per_frame = await context.render_scalar(self.config.params.max_object_count_per_frame, int)
        merge_gap                  = await context.render_scalar(self.config.params.merge_gap, float)
        bounding_box_padding       = await context.render_scalar(self.config.bounding_box_padding, float)
        return_tracks              = await context.render_scalar(self.config.return_tracks, bool)
        return_track_image         = await context.render_scalar(self.config.return_track_image, bool)
        return_frames              = await context.render_scalar(self.config.return_frames, bool)
        return_frame_image         = await context.render_scalar(self.config.return_frame_image, bool)
        return_metadata            = await context.render_scalar(self.config.return_metadata, bool)

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {min_confidence}")

        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError(f"'iou_threshold' must be between 0.0 and 1.0, got {iou_threshold}")

        if merge_gap < 0.0:
            raise ValueError(f"'merge_gap' must be >= 0.0, got {merge_gap}")

        if bounding_box_padding < 0.0:
            raise ValueError(f"'bounding_box_padding' must be >= 0.0, got {bounding_box_padding}")

        if not return_tracks and not return_frames:
            raise ValueError("Either 'return_tracks' or 'return_frames' must be true.")

        if return_frame_image and not return_frames:
            raise ValueError("'return_frame_image' requires 'return_frames' to be true.")

        if labels is not None and not isinstance(labels, list):
            labels = [ labels ]

        return {
            "labels":                     [ str(label) for label in labels ] if labels else None,
            "min_confidence":             min_confidence,
            "iou_threshold":              iou_threshold,
            "agnostic_nms":               agnostic_nms,
            "min_object_size":            min_object_size,
            "min_frame_count":            min_frame_count,
            "max_object_count_per_frame": max_object_count_per_frame,
            "merge_gap":                  merge_gap,
            "bounding_box_padding":       bounding_box_padding,
            "return_tracks":              return_tracks,
            "return_track_image":         return_track_image,
            "return_frames":              return_frames,
            "return_frame_image":         return_frame_image,
            "return_metadata":            return_metadata,
        }

    @abstractmethod
    async def _track_batch(
        self,
        frames_batch: List[ImageArrayValue],
        offsets_batch: List[float],
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]:
        """Run tracking on a batch of independent frame sequences. Each item in
        `frames_batch` is one video's ordered frames as an ImageArrayValue; the
        matching offset in `offsets_batch` is that video's timestamp for its
        first frame. Returns one item per input video: a tracking result dict
        when `streaming` is false, or an async iterator yielding per-frame and
        per-segment events (with a final done event carrying whatever wasn't
        already streamed) when it is true. The base class wraps the iterator
        as a StreamChunkIterator and applies per-chunk output rendering."""
        pass
