from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterable, AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ActiveSpeakerDetectionModelActionConfig
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

class ActiveSpeakerDetectionTaskAction(ModelTaskComponentAction):
    def __init__(self, config: ActiveSpeakerDetectionModelActionConfig):
        self.config: ActiveSpeakerDetectionModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        frames      = await context.render_image_array(self.config.frames)
        timestamps  = await context.render_array(self.config.timestamps) if self.config.timestamps is not None else None
        time_offset = await context.render_time(self.config.time_offset, 0.0)
        frame_rate  = await context.render_scalar(self.config.frame_rate, float)
        audio       = await context.render_audio(self.config.audio)
        tracks      = await context.render_variable(self.config.tracks)
        batch_size  = await context.render_variable(self.config.batch_size)
        streaming   = await context.render_scalar(self.config.streaming, bool)

        # `timestamps` overrides `frame_rate` / `time_offset` when set — same
        # rule as face-tracking, so a user who already paired per-frame pts
        # with `frames` upstream doesn't need to re-derive them here.
        if timestamps is None and (not frame_rate or frame_rate <= 0):
            raise ValueError(f"'frame_rate' must be > 0 when 'timestamps' is unset, got {frame_rate}")

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_frames, batch_timestamps, batch_offsets, batch_audios, batch_tracks in BatchSourceIterator((frames, timestamps, time_offset, audio, tracks), batch_size=batch_size or 1):
                    batch_results = await self._detect_batch(batch_frames, batch_timestamps, batch_offsets, batch_audios, batch_tracks, frame_rate, streaming, params, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            if isinstance(frames, StreamChunkIterator) and frames.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_frames, batch_timestamps, batch_offsets, batch_audios, batch_tracks in BatchSourceIterator((frames, timestamps, time_offset, audio, tracks), batch_size=batch_size or 1):
                batch_results = await self._detect_batch(batch_frames, batch_timestamps, batch_offsets, batch_audios, batch_tracks, frame_rate, streaming, params, context.cancellation_token)
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
        smoothing_window     = await context.render_scalar(self.config.params.smoothing_window, "time")
        threshold            = await context.render_scalar(self.config.params.threshold, float)
        min_segment_duration = await context.render_scalar(self.config.params.min_segment_duration, "time")
        merge_gap            = await context.render_scalar(self.config.params.merge_gap, "time")
        return_speakers      = await context.render_scalar(self.config.return_speakers, bool)
        return_frame_scores  = await context.render_scalar(self.config.return_frame_scores, bool)
        return_timeline      = await context.render_scalar(self.config.return_timeline, bool)
        return_metadata      = await context.render_scalar(self.config.return_metadata, bool)

        if smoothing_window < 0.0:
            raise ValueError(f"'smoothing_window' must be >= 0.0, got {smoothing_window}")

        if min_segment_duration < 0.0:
            raise ValueError(f"'min_segment_duration' must be >= 0.0, got {min_segment_duration}")

        if merge_gap < 0.0:
            raise ValueError(f"'merge_gap' must be >= 0.0, got {merge_gap}")

        return {
            "smoothing_window":     smoothing_window,
            "threshold":            threshold,
            "min_segment_duration": min_segment_duration,
            "merge_gap":            merge_gap,
            "return_speakers":      return_speakers,
            "return_frame_scores":  return_frame_scores,
            "return_timeline":      return_timeline,
            "return_metadata":      return_metadata,
        }

    @abstractmethod
    async def _detect_batch(
        self,
        frames: List[ImageArrayValue],
        timestamps: Optional[List[ArrayValue]],
        offsets: List[float],
        audios: List[MediaSource],
        tracks: List[Any],
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]:
        """Run speaker detection on a batch of independent (frames, audio, tracks)
        triples. Each item in `frames` is one video's ordered frames as an
        ImageArrayValue; the matching entries in `audios` and `tracks` pair
        with it by position. `tracks` holds the per-frame `detections` emitted
        by a face-tracking component — a list of `{number, timestamp, faces:
        [...]}` dicts, where each face carries a `track_id` and
        `bounding_box`. The matching offset in `offsets` is that video's
        timestamp for its first frame; `timestamps` optionally overrides the
        extrapolation with true per-frame pts. Returns one item per input
        video: a result dict when `streaming` is false, or an async iterator
        yielding per-segment events when it is true."""
        pass
