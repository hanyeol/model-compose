from mindor.dsl.schema.action import VideoAudioEncodingConfig, VideoEncoderConfig, AudioEncoderConfig
from mindor.core.foundation.media.encoding import VideoEncoderParams, AudioEncoderParams, VideoAudioEncodingParams
from mindor.core.foundation.variable.bitrate import parse_bitrate
from ..context import ComponentActionContext
from .base import ComponentAction

class MediaComponentAction(ComponentAction):
    """Base for actions that emit/consume video+audio with encoding configuration.

    Provides shared helpers to resolve DSL encoding configs into the normalized
    `VideoAudioEncodingParams` shape the driver/session/recorder layer expects.
    """

    async def _resolve_encoding_params(
        self, context: ComponentActionContext, config: VideoAudioEncodingConfig,
    ) -> VideoAudioEncodingParams:
        format = await context.render_variable(config.format) if config.format else None

        return VideoAudioEncodingParams(
            format=format,
            video=await self._resolve_video_encoder(context, config.video) if config.video else None,
            audio=await self._resolve_audio_encoder(context, config.audio) if config.audio else None,
        )

    async def _resolve_video_encoder(
        self, context: ComponentActionContext, config: VideoEncoderConfig,
    ) -> VideoEncoderParams:
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

    async def _resolve_audio_encoder(
        self, context: ComponentActionContext, config: AudioEncoderConfig,
    ) -> AudioEncoderParams:
        codec       = await context.render_variable(config.codec)       if config.codec       else None
        bitrate     = await context.render_variable(config.bitrate)     if config.bitrate     else None
        sample_rate = await context.render_variable(config.sample_rate) if config.sample_rate is not None else None
        channels    = await context.render_variable(config.channels)    if config.channels    is not None else None

        return AudioEncoderParams(
            codec=codec,
            bitrate=parse_bitrate(bitrate) if bitrate is not None else None,
            sample_rate=int(sample_rate) if sample_rate is not None else None,
            channels=int(channels) if channels is not None else None,
        )
