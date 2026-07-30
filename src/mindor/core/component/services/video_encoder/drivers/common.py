from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator, AsyncIterable
from abc import abstractmethod
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.image import ImageArrayValue
from PIL import Image as PILImage
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class VideoEncoderAction(MediaComponentAction):
    def __init__(self, config: VideoEncoderActionConfig):
        self.config: VideoEncoderActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        (video, audio), is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_videos, batch_audios in BatchSourceIterator((video, audio), batch_size=batch_size or 1):
                    batch_results = await self._encode_batch(batch_videos, batch_audios, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_videos, batch_audios in BatchSourceIterator((video, audio), batch_size=batch_size or 1):
                batch_results = await self._encode_batch(batch_videos, batch_audios, params, streaming, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Tuple[Any, Any], bool, bool]:
        video  = await context.render_video(self.config.video) if self.config.video is not None else None
        frames = await context.render_image_array(self.config.frames) if self.config.frames is not None else None
        audio  = await context.render_audio(self.config.audio) if self.config.audio is not None else None

        video = frames if video is None else video

        is_single_input = not isinstance(video, (list, StreamIterator, AsyncIterator)) and not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(video, (StreamIterator, AsyncIterator)) or isinstance(audio, (StreamIterator, AsyncIterator))

        return (video, audio), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        frame_rate = await context.render_variable(self.config.frame_rate) if self.config.frame_rate is not None else None
        encoding   = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else VideoAudioEncodingParams()

        return {
            "frame_rate": frame_rate,
            "encoding":   encoding,
        }

    async def _encode_batch(
        self,
        videos: List[Any],
        audios: Optional[List[MediaSource]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        results: List[VideoStreamResource] = []

        for index, video in enumerate(videos):
            audio = audios[index] if audios is not None else None
            if isinstance(video, ImageArrayValue):
                results.append(await self._encode_from_frames(video, audio, params["encoding"], params["frame_rate"], streaming, cancellation_token))
            else:
                results.append(await self._encode_from_video(video, audio, params["encoding"], streaming, cancellation_token))

        return results

    @abstractmethod
    async def _encode_from_video(
        self,
        video: MediaSource,
        audio: Optional[MediaSource],
        encoding: VideoAudioEncodingParams,
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        pass

    @abstractmethod
    async def _encode_from_frames(
        self,
        frames: AsyncIterable[PILImage.Image],
        audio: Optional[MediaSource],
        encoding: VideoAudioEncodingParams,
        frame_rate: Optional[float],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        pass
