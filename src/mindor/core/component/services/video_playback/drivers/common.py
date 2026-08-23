from __future__ import annotations

from typing import Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import VideoPlaybackActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class VideoPlaybackAction(ComponentAction):
    def __init__(self, config: VideoPlaybackActionConfig):
        self.config: VideoPlaybackActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        # Playback has no return value, so single/list/stream inputs all collapse
        # into one sequential consume-and-play loop. BatchSourceIterator normalizes
        # AsyncIterator/StreamIterator/list/single into batches, and batch_size
        # controls the fan-out to the sink when multiple inputs arrive together.
        async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
            await self._play_batch(batch_videos, params, context.cancellation_token)

        return None

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        window_title    = await context.render_variable(self.config.window_title)
        window_size     = await context.render_variable(self.config.window_size)
        fullscreen      = await context.render_scalar(self.config.fullscreen, bool)
        always_on_top   = await context.render_scalar(self.config.always_on_top, bool)
        borderless      = await context.render_scalar(self.config.borderless, bool)
        mute            = await context.render_scalar(self.config.mute, bool)
        volume          = await context.render_scalar(self.config.volume, int)
        duration        = await context.render_scalar(self.config.duration, "time", None)
        wait_for_finish = await context.render_scalar(self.config.wait_for_finish, bool)

        return {
            "window_title":    window_title,
            "window_size":     window_size,
            "fullscreen":      fullscreen,
            "always_on_top":   always_on_top,
            "borderless":      borderless,
            "mute":            mute,
            "volume":          volume,
            "duration":        duration,
            "wait_for_finish": wait_for_finish,
        }

    @abstractmethod
    async def _play_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass
