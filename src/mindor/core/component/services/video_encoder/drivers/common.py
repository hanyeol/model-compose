from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from PIL import Image as PILImage
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

class VideoEncoderAction:
    def __init__(self, config: VideoEncoderActionConfig):
        self.config: VideoEncoderActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)
        audio      = await context.render_audio(self.config.audio) if self.config.audio is not None else None
        params     = await self._resolve_params(context)

        if self.config.frames is not None:
            source = await context.render_image_array(self.config.frames)
        else:
            source = await context.render_video(self.config.video)

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator)) and self.config.frames is None
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for sources, audios in BatchSourceIterator((source, audio), batch_size=batch_size or 1):
                    batch_results = await self._process_batch(sources, audios, params, streaming, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for sources, audios in BatchSourceIterator((source, audio), batch_size=batch_size or 1):
                batch_results = await self._process_batch(sources, audios, params, streaming, loop)
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

        frame_rate    = await context.render_variable(self.config.frame_rate)   if self.config.frame_rate  is not None else None
        video_codec   = await context.render_variable(video_encoder.codec)      if video_encoder and video_encoder.codec      else default_video_codec
        video_bitrate = await context.render_variable(video_encoder.bitrate)    if video_encoder and video_encoder.bitrate    else None
        audio_codec   = await context.render_variable(audio_encoder.codec)      if audio_encoder and audio_encoder.codec      else default_audio_codec
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
        sources: List[Any],
        audios: Optional[List[MediaSource]],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[VideoStreamResource]]:
        return await asyncio.gather(*[
            self._process(source, audios[index] if audios is not None else None, params, streaming, loop)
            for index, source in enumerate(sources)
        ])

    async def _process(
        self,
        source: Any,
        audio: Optional[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[VideoStreamResource]:
        if source is None:
            logging.debug("Video encoder skipped because no input was provided.")
            return None

        if isinstance(source, list):
            return await self._encode_from_frames(source, audio, params, streaming, loop)

        return await self._encode_from_video(source, audio, params, streaming, loop)

    @abstractmethod
    async def _encode_from_frames(
        self,
        frames: List[PILImage.Image],
        audio: Optional[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> VideoStreamResource:
        pass

    @abstractmethod
    async def _encode_from_video(
        self,
        video: MediaSource,
        audio: Optional[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> VideoStreamResource:
        pass
