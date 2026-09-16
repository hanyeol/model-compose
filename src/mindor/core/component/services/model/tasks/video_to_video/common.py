from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Union, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoToVideoModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.image import load_image_from_stream, ImageStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.component.action.media import MediaInputPathResolver
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.image import convert as convert_image
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage
import os

class VideoToVideoTaskAction(ComponentAction):
    def __init__(self, config: VideoToVideoModelActionConfig):
        self.config: VideoToVideoModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source, is_single_input = await self._prepare_input(context)
        prompt          = await context.render_text(self.config.prompt) if self.config.prompt is not None else None
        negative_prompt = await context.render_text(self.config.negative_prompt) if self.config.negative_prompt is not None else None
        reference_image = await context.render_image(self.config.reference_image) if self.config.reference_image is not None else None
        batch_size      = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources, batch_prompts, batch_negatives, batch_references in BatchSourceIterator((source, prompt, negative_prompt, reference_image), batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_sources, batch_prompts, batch_negatives, batch_references, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_sources, batch_prompts, batch_negatives, batch_references in BatchSourceIterator((source, prompt, negative_prompt, reference_image), batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_sources, batch_prompts, batch_negatives, batch_references, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> tuple[Any, bool]:
        if self.config.frames is not None:
            frames = await context.render_image_array(self.config.frames, single_as_array=True)
            is_single_input = not isinstance(frames, (list, StreamIterator, AsyncIterator))

            return frames, is_single_input
        else:
            video = await context.render_video(self.config.video)
            is_single_input = not isinstance(video, (list, StreamIterator, AsyncIterator))

            return video, is_single_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_frames = await context.render_scalar(self.config.params.num_frames, int)
        fps        = await context.render_scalar(self.config.params.fps, int)
        height     = await context.render_scalar(self.config.params.height, int)
        width      = await context.render_scalar(self.config.params.width, int)
        seed       = await context.render_scalar(self.config.seed, int)

        return {
            "num_frames": num_frames,
            "fps":        fps,
            "height":     height,
            "width":      width,
            "seed":       seed,
        }

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

                frames.append(self._normalize_frame(PILImage.fromarray(array), width, height))

            return frames, fps
        finally:
            if spooled and path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    async def _collect_frames_from_image_array(
        self,
        value: ImageArrayValue,
        num_frames: Optional[int],
        width: Optional[int],
        height: Optional[int],
    ) -> List[PILImage.Image]:
        frames: List[PILImage.Image] = []

        async for image in value:
            if num_frames is not None and len(frames) >= num_frames:
                break

            if image is None:
                continue

            if isinstance(image, ImageStreamResource):
                image = await load_image_from_stream(image)

            frames.append(self._normalize_frame(image, width, height))

        return frames

    @staticmethod
    def _normalize_frame(
        image: PILImage.Image,
        width: Optional[int],
        height: Optional[int],
    ) -> PILImage.Image:
        return convert_image(image, width or image.width, height or image.height)

    @abstractmethod
    async def _generate_batch(
        self,
        sources: List[Union[MediaSource, ImageArrayValue]],
        prompts: Optional[List[Optional[str]]],
        negative_prompts: Optional[List[Optional[str]]],
        reference_images: Optional[List[Optional[PILImage.Image]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
