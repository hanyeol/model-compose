from __future__ import annotations

from typing import Optional, Dict, Any
from abc import abstractmethod
from dataclasses import dataclass
from mindor.dsl.schema.action import (
    ScreenCaptureActionConfig,
    ScreenCaptureVideoSource,
    ScreenCaptureAudioSource,
    VideoAudioEncodingConfig,
    VideoEncoderConfig,
    AudioEncoderConfig,
)
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.variable.bitrate import parse_bitrate
from mindor.core.utils.enum import coerce_enum
from ..base import ComponentActionContext

@dataclass
class VideoEncoderParams:
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    resolution: Optional[str] = None
    fps: Optional[float] = None

@dataclass
class AudioEncoderParams:
    codec: Optional[str] = None
    bitrate: Optional[int] = None

@dataclass
class VideoAudioEncodingParams:
    """Rendered encoding parameters ready for the driver layer.

    Values here are already resolved from variable references (${input.foo})
    and normalized (e.g. bitrate parsed to bits per second), so downstream
    consumers don't need to touch the DSL config again.
    """
    format: Optional[str] = None
    video: Optional[VideoEncoderParams] = None
    audio: Optional[AudioEncoderParams] = None

class ScreenCaptureAction:
    def __init__(self, config: ScreenCaptureActionConfig):
        self.config: ScreenCaptureActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._capture(params)

        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        video_source  = await context.render_variable(self.config.video_source)
        audio_source  = await context.render_variable(self.config.audio_source)
        include_video = await context.render_variable(self.config.include_video)
        include_audio = await context.render_variable(self.config.include_audio)
        display       = await context.render_variable(self.config.display)
        region        = await self._resolve_region(context) if self.config.region is not None else None
        framerate     = await context.render_variable(self.config.framerate)
        encoding      = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else None
        duration      = await context.render_variable(self.config.duration) if self.config.duration is not None else None

        video_source = coerce_enum(video_source, ScreenCaptureVideoSource, "video_source")
        framerate    = float(framerate)
        duration     = parse_time(duration) if duration is not None else None

        if framerate <= 0:
            raise ValueError(f"'framerate' must be > 0, got {framerate}")

        if duration is not None and duration <= 0:
            raise ValueError(f"'duration' must be > 0, got {duration}")

        if video_source == ScreenCaptureVideoSource.REGION and region is None:
            raise ValueError("'region' must be provided when video_source='region'.")

        return {
            "video_source":  video_source,
            "display":       int(display),
            "region":        region,
            "include_video": bool(include_video),
            "include_audio": bool(include_audio),
            "audio_source":  coerce_enum(audio_source, ScreenCaptureAudioSource, "audio_source"),
            "framerate":     framerate,
            "encoding":      encoding,
            "duration":      duration,
        }

    async def _resolve_encoding_params(self, context: ComponentActionContext, config: VideoAudioEncodingConfig) -> VideoAudioEncodingParams:
        format = await context.render_variable(config.format) if config.format else None

        return VideoAudioEncodingParams(
            format=format,
            video=await self._resolve_video_encoder(context, config.video) if config.video else None,
            audio=await self._resolve_audio_encoder(context, config.audio) if config.audio else None,
        )

    async def _resolve_video_encoder(self, context: ComponentActionContext, config: VideoEncoderConfig) -> VideoEncoderParams:
        codec      = await context.render_variable(config.codec)      if config.codec      else None
        bitrate    = await context.render_variable(config.bitrate)    if config.bitrate    else None
        resolution = await context.render_variable(config.resolution) if config.resolution else None
        fps        = await context.render_variable(config.fps)        if config.fps        else None

        return VideoEncoderParams(
            codec=codec,
            bitrate=parse_bitrate(bitrate) if bitrate is not None else None,
            resolution=resolution,
            fps=float(fps) if fps is not None else None,
        )

    async def _resolve_audio_encoder(self, context: ComponentActionContext, config: AudioEncoderConfig) -> AudioEncoderParams:
        codec   = await context.render_variable(config.codec)   if config.codec   else None
        bitrate = await context.render_variable(config.bitrate) if config.bitrate else None

        return AudioEncoderParams(
            codec=codec,
            bitrate=parse_bitrate(bitrate) if bitrate is not None else None,
        )

    async def _resolve_region(self, context: ComponentActionContext) -> Dict[str, int]:
        x      = int(await context.render_variable(self.config.region.x))
        y      = int(await context.render_variable(self.config.region.y))
        width  = int(await context.render_variable(self.config.region.width))
        height = int(await context.render_variable(self.config.region.height))

        if width <= 0 or height <= 0:
            raise ValueError(f"region size must be > 0, got width={width}, height={height}")

        if x < 0 or y < 0:
            raise ValueError(f"region origin must be >= 0, got x={x}, y={y}")

        return { "x": x, "y": y, "width": width, "height": height }

    @abstractmethod
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run the capture and return a dict shaped like:

            { "video": VideoStreamResource | None,
              "audio": AudioStreamResource | None,
              "capture_pts": float }

        `capture_pts` is a monotonic wall-clock anchor (seconds) taken when
        capture starts, so downstream consumers can align chunks to an absolute
        broadcast timeline.
        """
        pass
