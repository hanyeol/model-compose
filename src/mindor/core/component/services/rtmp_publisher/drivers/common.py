from __future__ import annotations

from typing import Optional, List, Any

from abc import abstractmethod
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ....action.media import VideoAudioEncodingResolver
from ..base import ComponentActionContext

class RtmpPublisherAction(ComponentAction):
    def __init__(self, config: RtmpPublisherActionConfig):
        self.config: RtmpPublisherActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video = await context.render_video(self.config.video) if self.config.video is not None else None
        audio = await context.render_audio(self.config.audio) if self.config.audio is not None else None
        url   = await context.render_variable(self.config.url)

        encoding = await VideoAudioEncodingResolver().resolve(context, self.config.encoding) if self.config.encoding else VideoAudioEncodingParams()

        # Each item runs as its own publish so a peer-side disconnect
        # (e.g. YouTube ending the stream) doesn't bleed into the next one.
        async for videos, audios in BatchSourceIterator((video, audio), batch_size=1):
            await self._publish_batch(videos, audios, url, encoding, context.cancellation_token)

        return None

    @abstractmethod
    async def _publish_batch(
        self,
        videos: Optional[List[MediaSource]],
        audios: Optional[List[MediaSource]],
        url: str,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass
