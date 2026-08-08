from __future__ import annotations

from typing import Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import AudioPlaybackActionConfig, AudioPlaybackSink
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.media import MediaSource
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class AudioPlaybackAction(ComponentAction):
    def __init__(self, config: AudioPlaybackActionConfig):
        self.config: AudioPlaybackActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        # Playback has no return value, so single/list/stream inputs all collapse
        # into one sequential consume-and-play loop. BatchSourceIterator normalizes
        # AsyncIterator/StreamIterator/list/single into batches, and batch_size
        # controls the fan-out to the sink when multiple inputs arrive together.
        async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
            await self._play_batch(batch_audios, params, context.cancellation_token)

        return None

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        sink            = await context.render_variable(self.config.sink)
        device          = await context.render_variable(self.config.device)
        volume          = await context.render_scalar(self.config.volume, float)
        duration        = await context.render_time(self.config.duration, None)
        wait_for_finish = await context.render_scalar(self.config.wait_for_finish, bool)

        return {
            "sink":            AudioPlaybackSink(sink) if not isinstance(sink, AudioPlaybackSink) else sink,
            "device":          device,
            "volume":          volume,
            "duration":        duration,
            "wait_for_finish": wait_for_finish,
        }

    @abstractmethod
    async def _play_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass
