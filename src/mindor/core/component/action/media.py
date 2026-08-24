from __future__ import annotations

from typing import Optional, List, Tuple, Literal
from mindor.dsl.schema.action import VideoAudioEncodingConfig, VideoEncoderConfig, AudioEncoderConfig
from mindor.core.foundation.media.encoding import VideoEncoderParams, AudioEncoderParams, VideoAudioEncodingParams
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.audio import is_streamable_audio_format
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.logger import logging
from ..context import ComponentActionContext

class MediaInputPathResolver:
    """Resolve a MediaSource to a filesystem path (or None for pipe:0).

    Encapsulates the shared decision logic for how ffmpeg/ffprobe/opencv/etc.
    receive a media input: use its existing file path, feed a streamable
    format via stdin, or spool the stream to a temp file so the tool can seek.
    """

    async def resolve(
        self,
        source: MediaSource,
        streamable_media: Optional[List[Literal[ "video", "audio" ]]] = None,
        default_format: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        """Return ``(path, spooled)`` for the given source.

        - FileStreamResource: returns (path, False), no spooling.
        - ``streamable_media`` lists the domains (``"audio"`` and/or ``"video"``)
          whose streamable formats may be fed via pipe:0; matching sources return
          (None, False).
        - Otherwise: spools to a temp file and returns (path, True); the caller
          owns the cleanup. ``default_format`` sets the spool file extension
          when ``source.format`` is missing.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if streamable_media:
            if "audio" in streamable_media and is_streamable_audio_format(source.format):
                return None, False

            if "video" in streamable_media and is_streamable_video_format(source.format):
                return None, False

        logging.debug("Spooling non-streamable input (format=%s) to a temp file", source.format)

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format or default_format)

        return spooled_path, True

class VideoAudioEncodingResolver:
    """Turn DSL VideoAudioEncodingConfig into normalized VideoAudioEncodingParams."""

    async def resolve(
        self,
        context: ComponentActionContext,
        encoding: VideoAudioEncodingConfig,
    ) -> VideoAudioEncodingParams:
        format = await context.render_scalar(encoding.format, str)

        return VideoAudioEncodingParams(
            format=format,
            video= await self.resolve_video(context, encoding.video) if encoding.video else None,
            audio= await self.resolve_audio(context, encoding.audio) if encoding.audio else None,
        )

    async def resolve_video(
        self,
        context: ComponentActionContext,
        video: VideoEncoderConfig,
    ) -> VideoEncoderParams:
        codec      = await context.render_scalar(video.codec, str)
        bitrate    = await context.render_scalar(video.bitrate, "decimal")
        resolution = await context.render_scalar(video.resolution, str)
        fps        = await context.render_scalar(video.fps, float)

        return VideoEncoderParams(
            codec=codec,
            bitrate=bitrate,
            resolution=resolution,
            fps=fps,
        )

    async def resolve_audio(
        self,
        context: ComponentActionContext,
        audio: AudioEncoderConfig,
    ) -> AudioEncoderParams:
        codec       = await context.render_scalar(audio.codec, str)
        bitrate     = await context.render_scalar(audio.bitrate, "decimal")
        sample_rate = await context.render_scalar(audio.sample_rate, int)
        channels    = await context.render_scalar(audio.channels, int)

        return AudioEncoderParams(
            codec=codec,
            bitrate=bitrate,
            sample_rate=sample_rate,
            channels=channels,
        )
