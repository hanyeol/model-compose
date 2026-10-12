from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.action import VideoToVideoModelActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.image import load_image_from_stream, ImageStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.component.action.media import MediaInputPathResolver
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.image import convert as convert_image
from ...base import ComponentActionContext, ModelTaskComponentAction
from PIL import Image as PILImage
import os

class VideoToVideoTaskAction(ModelTaskComponentAction):
    def __init__(self, config: VideoToVideoModelActionConfig):
        self.config: VideoToVideoModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @abstractmethod
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Tuple[Any, ...], bool, bool]:
        pass

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    async def _collect_frames_from_video(
        self,
        video: MediaSource,
        num_frames: Optional[int],
        width: Optional[int],
        height: Optional[int],
    ) -> Tuple[List[PILImage.Image], Optional[float]]:
        """Return the sampled frames plus the source's native fps (when detectable).

        Callers use the fps hint to preserve the input clip's playback duration
        when the action doesn't specify one explicitly.
        """
        import imageio.v3 as iio

        # imageio picks its backend by extension, so probe the container when
        # the upstream source didn't carry one (e.g. Gradio uploads).
        path, spooled = await MediaInputPathResolver().resolve(video, detect_format=True)

        if path is None:
            raise ValueError("Input video must resolve to a filesystem path.")

        try:
            metadata = iio.immeta(path)
            fps: Optional[float] = metadata.get("fps") if isinstance(metadata, dict) else None
            frames: List[PILImage.Image] = []

            for index, array in enumerate(iio.imiter(path)):
                if num_frames is not None and index >= num_frames:
                    break

                frames.append(self._preprocess_frame(PILImage.fromarray(array), width, height))

            return frames, fps
        finally:
            if spooled and path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    async def _collect_frames_from_image_array(
        self,
        images: ImageArrayValue,
        num_frames: Optional[int],
        width: Optional[int],
        height: Optional[int],
    ) -> List[PILImage.Image]:
        frames: List[PILImage.Image] = []

        async for image in images:
            if num_frames is not None and len(frames) >= num_frames:
                break

            if image is None:
                continue

            if isinstance(image, ImageStreamResource):
                image = await load_image_from_stream(image)

            frames.append(self._preprocess_frame(image, width, height))

        return frames

    @staticmethod
    def _preprocess_frame(
        image: PILImage.Image,
        width: Optional[int],
        height: Optional[int],
    ) -> PILImage.Image:
        return convert_image(image, width or image.width, height or image.height)

    @abstractmethod
    async def _generate_batch(
        self,
        inputs: Tuple[Any, ...],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
