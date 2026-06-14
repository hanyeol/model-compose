from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoConverterActionConfig, VideoAudioCodecConfig
from mindor.core.utils.iterator import AsyncSourceIterator
from mindor.core.utils.video import VideoStreamResource
from mindor.core.utils.media import MediaSource
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

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        is_stream_input  = isinstance(video, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or (is_stream_input and is_direct_output)

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_videos in AsyncSourceIterator(video, batch_size=batch_size or 1):
                    processed_videos = await self._process_batch(batch_videos, context)
                    for processed_video in processed_videos:
                        context.register_source("result[]", processed_video)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else processed_video

            return _stream_output_generator()

        is_single_input: bool = not isinstance(video, (list, AsyncIterator))
        results = []
        async for batch_videos in AsyncSourceIterator(video, batch_size=batch_size or 1):
            processed_videos = await self._process_batch(batch_videos, context)
            results.extend(processed_videos)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(self, videos: List[MediaSource], context: ComponentActionContext) -> List[Optional[VideoStreamResource]]:
        params = await self._resolve_params(context)

        return await asyncio.gather(*[
            self._process(video, params) for video in videos
        ])

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format     = await context.render_variable(self.config.format) if self.config.format else "mp4"
        video_codec, audio_codec = await self._resolve_codec(context, format)
        bitrate    = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        resolution = await context.render_variable(self.config.resolution) if self.config.resolution else None
        fps        = await context.render_variable(self.config.fps) if self.config.fps else None

        return {
            "format":      format,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "bitrate":     bitrate,
            "resolution":  resolution,
            "fps":         fps,
        }

    async def _resolve_codec(self, context: ComponentActionContext, format: str) -> Tuple[Optional[str], Optional[str]]:
        default_video_codec, default_audio_codec = _FORMAT_CODEC_MAP.get(format, (None, None))

        if isinstance(self.config.codec, VideoAudioCodecConfig):
            video_codec = await context.render_variable(self.config.codec.video) if self.config.codec.video else default_video_codec
            audio_codec = await context.render_variable(self.config.codec.audio) if self.config.codec.audio else default_audio_codec
        elif self.config.codec:
            video_codec = await context.render_variable(self.config.codec)
            audio_codec = default_audio_codec
        else:
            video_codec = default_video_codec
            audio_codec = default_audio_codec

        return video_codec, audio_codec

    async def _process(self, video: MediaSource, params: Dict[str, Any]) -> Optional[VideoStreamResource]:
        if video is None:
            logging.debug("Video converter skipped because no video was provided.")
            return None

        return await self._convert(
            video,
            params["format"],
            params["video_codec"],
            params["audio_codec"],
            params["bitrate"],
            params["resolution"],
            params["fps"],
        )

    @abstractmethod
    async def _convert(
        self,
        source: MediaSource,
        format: str,
        video_codec: Optional[str],
        audio_codec: Optional[str],
        bitrate: Optional[str],
        resolution: Optional[str],
        fps: Optional[str],
    ) -> VideoStreamResource:
        pass
