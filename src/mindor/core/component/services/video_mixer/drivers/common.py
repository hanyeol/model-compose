from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator, Iterator
from abc import abstractmethod
from mindor.dsl.schema.action import (
    VideoMixerActionConfig,
    VideoMixerActionMethod,
    VideoMixerOverlayAudioMode,
    VideoMixerOverlayDurationMode,
    VideoOverlayPlacement,
)
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.video import VideoArrayValue
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ....action.media import VideoAudioEncodingResolver
from ..base import ComponentActionContext
import asyncio

class VideoMixerAction(ComponentAction):
    def __init__(self, config: VideoMixerActionConfig):
        self.config: VideoMixerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_scalar(self.config.streaming, bool, False)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_results = await self._process_batch(self.config.method, batch_inputs, params, streaming, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: VideoMixerActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method == VideoMixerActionMethod.CONCAT:
            videos = await context.render_video_array(self.config.videos)

            is_single_input    = isinstance(videos, VideoArrayValue)
            is_streaming_input = isinstance(videos, (StreamIterator, AsyncIterator))

            return videos, is_single_input, is_streaming_input

        if method == VideoMixerActionMethod.OVERLAY:
            video     = await context.render_video(self.config.video)
            overlay   = await context.render_video_array(self.config.overlay, single_as_array=True)
            placement = await self._render_overlay_placement(context)

            is_single_input    = not isinstance(video, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(video, (StreamIterator, AsyncIterator))

            return (video, overlay, placement), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported video mixer action method: {method}")

    async def _resolve_params(
        self,
        method: VideoMixerActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == VideoMixerActionMethod.CONCAT:
            encoding  = await VideoAudioEncodingResolver().resolve(context, self.config.encoding) if self.config.encoding else VideoAudioEncodingParams()
            crossfade = await context.render_scalar(self.config.crossfade, "time")

            return {
                "encoding":  encoding,
                "crossfade": crossfade,
            }

        if method == VideoMixerActionMethod.OVERLAY:
            encoding      = await VideoAudioEncodingResolver().resolve(context, self.config.encoding) if self.config.encoding else VideoAudioEncodingParams()
            audio_mode    = await context.render_variable(self.config.audio_mode)
            duration_mode = await context.render_variable(self.config.duration_mode)

            try:
                audio_mode = VideoMixerOverlayAudioMode(audio_mode)
            except ValueError:
                raise ValueError(f"Invalid audio_mode: {audio_mode}")

            try:
                duration_mode = VideoMixerOverlayDurationMode(duration_mode)
            except ValueError:
                raise ValueError(f"Invalid duration_mode: {duration_mode}")

            return {
                "encoding":      encoding,
                "audio_mode":    audio_mode,
                "duration_mode": duration_mode,
            }

        raise ValueError(f"Unsupported video mixer action method: {method}")

    async def _process_batch(
        self,
        method: VideoMixerActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        if method in (VideoMixerActionMethod.OVERLAY, ):
            inputs = list(zip(*inputs))

        return await asyncio.gather(*[
            self._process(method, input, params, streaming, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: VideoMixerActionMethod,
        input: Any,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        if method == VideoMixerActionMethod.CONCAT:
            videos = await input.collect()

            if len(videos) < 2:
                raise ValueError("concat requires at least two videos.")

            return await self._concat(videos, params, streaming, cancellation_token)

        if method == VideoMixerActionMethod.OVERLAY:
            video, overlays, placements = input
            overlays   = await overlays.collect()
            placements = await placements.collect()

            # Broadcast a single placement across all overlays; otherwise pair by position.
            if len(placements) == 1 and len(overlays) > 1:
                placements = [ placements[0] ] * len(overlays)

            if len(placements) != len(overlays):
                raise ValueError(
                    f"overlay/placement cardinality mismatch: {len(overlays)} overlays vs {len(placements)} placements."
                )

            return await self._overlay(
                video,
                overlays,
                placements,
                params,
                streaming,
                cancellation_token,
            )

        raise ValueError(f"Unsupported video mixer action method: {method}")

    async def _render_overlay_placement(self, context: ComponentActionContext) -> ArrayValue:
        """Resolve the overlay `placement` field into an `ArrayValue` of placements paired with overlays.

        `self.config.placement` may be a single `VideoOverlayPlacement`, a
        list of placements, a template string, or a list of template strings.
        `render_array` with `single_as_array=True` renders any template refs
        and normalizes single values into a one-element `ArrayValue`, so
        downstream always sees an iterable of placement entries. `ArrayValue`
        isn't seen as iterable by `BatchSourceIterator`, so the placements
        travel as a single unit alongside the base video instead of being
        consumed element-by-element.
        """
        placement = await context.render_array(self.config.placement, single_as_array=True)

        if placement is None:
            return ArrayValue([ VideoOverlayPlacement() ])

        return ArrayValue([ self._as_overlay_placement(item) async for item in placement ])

    @staticmethod
    def _as_overlay_placement(value: Any) -> VideoOverlayPlacement:
        if isinstance(value, VideoOverlayPlacement):
            return value

        if isinstance(value, dict):
            return VideoOverlayPlacement.model_validate(value)

        raise ValueError(f"'placement' entry must be a placement object or dict, got {type(value).__name__}")

    @abstractmethod
    async def _concat(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        pass

    @abstractmethod
    async def _overlay(
        self,
        video: MediaSource,
        overlays: List[MediaSource],
        placements: List[VideoOverlayPlacement],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        pass
