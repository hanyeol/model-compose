from mindor.dsl.schema.action import VideoAudioEncodingConfig, VideoEncoderConfig, AudioEncoderConfig
from mindor.core.foundation.media.encoding import VideoEncoderParams, AudioEncoderParams, VideoAudioEncodingParams
from ..context import ComponentActionContext
from .base import ComponentAction

class MediaComponentAction(ComponentAction):
    """Base for actions that emit/consume video+audio with encoding configuration.

    Provides shared helpers to resolve DSL encoding configs into the normalized
    `VideoAudioEncodingParams` shape the driver/session/recorder layer expects.
    """
    async def _resolve_encoding_params(
        self, context: ComponentActionContext, encoding: VideoAudioEncodingConfig,
    ) -> VideoAudioEncodingParams:
        format = await context.render_scalar(encoding.format, str)

        return VideoAudioEncodingParams(
            format=format,
            video= await self._resolve_video_encoder(context, encoding.video) if encoding.video else None,
            audio= await self._resolve_audio_encoder(context, encoding.audio) if encoding.audio else None,
        )

    async def _resolve_video_encoder(
        self, context: ComponentActionContext, video: VideoEncoderConfig,
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

    async def _resolve_audio_encoder(
        self, context: ComponentActionContext, audio: AudioEncoderConfig,
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
