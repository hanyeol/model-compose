from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.logger import logging
from PIL import Image as PILImage
from ..base import ComponentActionContext
import asyncio

# RTMP is virtually always flv-wrapped h264/aac.
_DEFAULT_FORMAT: str = "flv"
_DEFAULT_VIDEO_CODEC: str = "libx264"
_DEFAULT_AUDIO_CODEC: str = "aac"

class RtmpPublisherAction:
    def __init__(self, config: RtmpPublisherActionConfig):
        self.config: RtmpPublisherActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        video, audio, url = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        # Unlike video_encoder, publishing has no return value,
        # so single vs. batch and streaming vs. non-streaming inputs collapse into
        # the same sequential consume-and-publish loop. batch_size controls the
        # fan-out when multiple destination URLs are provided.
        async for batch_videos, batch_audios, batch_urls in BatchSourceIterator((video, audio, url), batch_size=batch_size or 1):
            await self._process_batch(batch_videos, batch_audios, batch_urls, params, loop, context.cancellation_token)

        return None

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, Any]:
        video  = await context.render_video(self.config.video) if self.config.video is not None else None
        frames = await context.render_image_array(self.config.frames) if self.config.frames is not None else None
        audio  = await context.render_audio(self.config.audio) if self.config.audio is not None else None
        url    = await context.render_variable(self.config.url)

        video = frames if frames is not None else video

        return video, audio, url

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        encoding_config = self.config.encoding
        video_encoder = encoding_config.video if encoding_config else None
        audio_encoder = encoding_config.audio if encoding_config else None

        format = await context.render_variable(encoding_config.format) if encoding_config and encoding_config.format else _DEFAULT_FORMAT

        frame_rate    = await context.render_variable(self.config.frame_rate)   if self.config.frame_rate  is not None else None
        video_codec   = await context.render_variable(video_encoder.codec)      if video_encoder and video_encoder.codec      else _DEFAULT_VIDEO_CODEC
        video_bitrate = await context.render_variable(video_encoder.bitrate)    if video_encoder and video_encoder.bitrate    else None
        audio_codec   = await context.render_variable(audio_encoder.codec)      if audio_encoder and audio_encoder.codec      else _DEFAULT_AUDIO_CODEC
        audio_bitrate = await context.render_variable(audio_encoder.bitrate)    if audio_encoder and audio_encoder.bitrate    else None
        resolution    = await context.render_variable(video_encoder.resolution) if video_encoder and video_encoder.resolution else None
        fps           = await context.render_variable(video_encoder.fps)        if video_encoder and video_encoder.fps        else None

        return {
            "format":        format,
            "frame_rate":    frame_rate,
            "video_codec":   video_codec,
            "video_bitrate": video_bitrate,
            "audio_codec":   audio_codec,
            "audio_bitrate": audio_bitrate,
            "resolution":    resolution,
            "fps":           fps,
        }

    async def _process_batch(
        self,
        videos: Optional[List[Any]],
        audios: Optional[List[MediaSource]],
        urls: List[str],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        await asyncio.gather(*[
            self._process(
                videos[index] if videos is not None else None,
                audios[index] if audios is not None else None,
                urls[index],
                params, loop, cancellation_token,
            )
            for index in range(len(urls))
        ])

    async def _process(
        self,
        video: Any,
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        if video is None and audio is None:
            logging.debug("RTMP publisher skipped because no input was provided.")
            return

        if video is None:
            await self._publish_audio_only(audio, url, params, loop, cancellation_token)
            return

        if isinstance(video, ImageArrayValue):
            await self._publish_from_frames(video.values, audio, url, params, loop, cancellation_token)
            return

        await self._publish_from_video(video, audio, url, params, loop, cancellation_token)

    @abstractmethod
    async def _publish_from_video(
        self,
        video: MediaSource,
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass

    @abstractmethod
    async def _publish_from_frames(
        self,
        frames: List[PILImage.Image],
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass

    @abstractmethod
    async def _publish_audio_only(
        self,
        audio: MediaSource,
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass
