from __future__ import annotations

from typing import Optional, Dict, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio, ulid

# RTMP is virtually always flv-wrapped h264/aac.
_DEFAULT_FORMAT: str = "flv"
_DEFAULT_VIDEO_CODEC: str = "libx264"
_DEFAULT_AUDIO_CODEC: str = "aac"

class RtmpPublisherAction:
    def __init__(self, config: RtmpPublisherActionConfig):
        self.config: RtmpPublisherActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        video = await context.render_video(self.config.video) if self.config.video is not None else None
        audio = await context.render_audio(self.config.audio) if self.config.audio is not None else None
        url   = await context.render_variable(self.config.url)

        params = await self._resolve_params(context)

        # Iterable inputs (list or async iterator) mean "keep the RTMP
        # session open across each item". A fresh ULID names the session
        # so the driver can hold one long-lived ffmpeg process for this
        # action's lifetime. Single-value inputs run as one-shot publishes:
        # one ffmpeg process, no persistent session.
        is_multiple_video = isinstance(video, (list, StreamIterator, AsyncIterator))
        is_multiple_audio = isinstance(audio, (list, StreamIterator, AsyncIterator))

        session = ulid.ulid() if is_multiple_video or is_multiple_audio else None

        try:
            async for videos, audios in BatchSourceIterator((video, audio), batch_size=1):
                video = videos[0] if videos is not None else None
                audio = audios[0] if audios is not None else None
                await self._process(video, audio, url, session, params, loop, context.cancellation_token)
        finally:
            # The session's persistent publisher exists for the batch loop
            # only. Tear it down when the loop ends (normal completion,
            # cancellation, or exception) so we don't leak the ffmpeg
            # process past the action's lifetime.
            if session is not None:
                await self._cleanup(session)

        return None

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        encoding_config = self.config.encoding
        video_encoder = encoding_config.video if encoding_config else None
        audio_encoder = encoding_config.audio if encoding_config else None

        format = await context.render_variable(encoding_config.format) if encoding_config and encoding_config.format else _DEFAULT_FORMAT

        video_codec   = await context.render_variable(video_encoder.codec)      if video_encoder and video_encoder.codec      else _DEFAULT_VIDEO_CODEC
        video_bitrate = await context.render_variable(video_encoder.bitrate)    if video_encoder and video_encoder.bitrate    else None
        audio_codec   = await context.render_variable(audio_encoder.codec)      if audio_encoder and audio_encoder.codec      else _DEFAULT_AUDIO_CODEC
        audio_bitrate = await context.render_variable(audio_encoder.bitrate)    if audio_encoder and audio_encoder.bitrate    else None
        resolution    = await context.render_variable(video_encoder.resolution) if video_encoder and video_encoder.resolution else None
        fps           = await context.render_variable(video_encoder.fps)        if video_encoder and video_encoder.fps        else None

        return {
            "format":        format,
            "video_codec":   video_codec,
            "video_bitrate": video_bitrate,
            "audio_codec":   audio_codec,
            "audio_bitrate": audio_bitrate,
            "resolution":    resolution,
            "fps":           fps,
        }

    async def _process(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        session: Optional[str],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        if video is None and audio is None:
            logging.debug("RTMP publisher skipped because no input was provided.")
            return

        await self._publish(video, audio, url, session, params, loop, cancellation_token)

    @abstractmethod
    async def _publish(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        session: Optional[str],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass

    @abstractmethod
    async def _cleanup(self, session: str) -> None:
        """Tear down the persistent RTMP session opened for `session`."""
        pass
