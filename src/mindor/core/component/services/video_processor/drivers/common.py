from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import (
    VideoProcessorActionConfig,
    VideoProcessorActionMethod,
    VideoScaleMode,
    VideoFlipDirection,
)
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class VideoProcessorAction(MediaComponentAction):
    def __init__(self, config: VideoProcessorActionConfig):
        self.config: VideoProcessorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_single_input  = not isinstance(video, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_videos, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()

        results = []
        async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
            batch_results = await self._process_batch(self.config.method, batch_videos, params, context.cancellation_token)
            results.extend(batch_results)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: VideoProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        encoding = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else VideoAudioEncodingParams()

        if method == VideoProcessorActionMethod.RESIZE:
            width      = await context.render_scalar(self.config.width, int)
            height     = await context.render_scalar(self.config.height, int)
            scale_mode = await context.render_variable(self.config.scale_mode)

            if width is None and height is None:
                raise ValueError("At least one of 'width' or 'height' must be specified for 'resize' method")

            try:
                scale_mode = VideoScaleMode(scale_mode)
            except ValueError:
                raise ValueError(f"Invalid scale_mode: {scale_mode}")

            return { "encoding": encoding, "width": width, "height": height, "scale_mode": scale_mode }

        if method == VideoProcessorActionMethod.CROP:
            x      = await context.render_scalar(self.config.x, int)
            y      = await context.render_scalar(self.config.y, int)
            width  = await context.render_scalar(self.config.width, int)
            height = await context.render_scalar(self.config.height, int)

            if x is None or y is None or width is None or height is None:
                raise ValueError("'x', 'y', 'width', and 'height' must all be specified for 'crop' method")

            return { "encoding": encoding, "x": x, "y": y, "width": width, "height": height }

        if method == VideoProcessorActionMethod.PAD:
            left   = await context.render_scalar(self.config.left,   int) or 0
            right  = await context.render_scalar(self.config.right,  int) or 0
            top    = await context.render_scalar(self.config.top,    int) or 0
            bottom = await context.render_scalar(self.config.bottom, int) or 0
            color  = await context.render_variable(self.config.color)

            if left < 0 or right < 0 or top < 0 or bottom < 0:
                raise ValueError("Padding values must be non-negative for 'pad' method")

            return { "encoding": encoding, "left": left, "right": right, "top": top, "bottom": bottom, "color": color }

        if method == VideoProcessorActionMethod.FLIP:
            direction = await context.render_variable(self.config.direction)

            if direction is None:
                raise ValueError("'direction' must be specified for 'flip' method")

            try:
                direction = VideoFlipDirection(direction)
            except ValueError:
                raise ValueError(f"Invalid flip direction: {direction}")

            return { "encoding": encoding, "direction": direction }

        if method == VideoProcessorActionMethod.ROTATE:
            angle  = await context.render_scalar(self.config.angle, float)
            expand = await context.render_scalar(self.config.expand, bool)

            if angle is None:
                raise ValueError("'angle' must be specified for 'rotate' method")

            return { "encoding": encoding, "angle": angle, "expand": bool(expand) if expand is not None else True }

        raise ValueError(f"Unsupported video processing action method: {method}")

    @abstractmethod
    async def _process_batch(
        self,
        method: VideoProcessorActionMethod,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
