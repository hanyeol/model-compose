from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

_FORMAT_CODEC_MAP: Dict[str, Tuple[str, str]] = {
    "mp4":  ("libx264",    "aac"),
    "m4v":  ("libx264",    "aac"),
    "mov":  ("libx264",    "aac"),
    "mkv":  ("libx264",    "aac"),
    "webm": ("libvpx-vp9", "libopus"),
    "avi":  ("mpeg4",      "libmp3lame"),
    "ogv":  ("libtheora",  "libvorbis"),
}

class VideoConverterAction:
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(video, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_videos, params, loop, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_videos, params, loop, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        encoding_config = self.config.encoding
        video_encoder = encoding_config.video if encoding_config else None
        audio_encoder = encoding_config.audio if encoding_config else None

        format = await context.render_variable(encoding_config.format) if encoding_config and encoding_config.format else "mp4"
        default_video_codec, default_audio_codec = _FORMAT_CODEC_MAP.get(format, (None, None))

        video_codec   = await context.render_variable(video_encoder.codec)      if video_encoder and video_encoder.codec      else default_video_codec
        video_bitrate = await context.render_variable(video_encoder.bitrate)    if video_encoder and video_encoder.bitrate    else None
        audio_codec   = await context.render_variable(audio_encoder.codec)      if audio_encoder and audio_encoder.codec      else default_audio_codec
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

    async def _process_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Optional[VideoStreamResource]]:
        return await asyncio.gather(*[
            self._process(video, params, loop, cancellation_token) for video in videos
        ])

    async def _process(
        self,
        video: MediaSource,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Optional[VideoStreamResource]:
        if video is None:
            logging.debug("Video converter skipped because no video was provided.")
            return None

        return await self._convert(
            video,
            params["format"],
            params["video_codec"],
            params["video_bitrate"],
            params["audio_codec"],
            params["audio_bitrate"],
            params["resolution"],
            params["fps"],
            loop,
            cancellation_token,
        )

    @abstractmethod
    async def _convert(
        self,
        source: MediaSource,
        format: str,
        video_codec: Optional[str],
        video_bitrate: Optional[str],
        audio_codec: Optional[str],
        audio_bitrate: Optional[str],
        resolution: Optional[str],
        fps: Optional[str],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        pass
