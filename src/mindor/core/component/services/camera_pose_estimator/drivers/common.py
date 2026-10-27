from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import CameraPoseEstimatorActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.streaming.resources import StreamResource, save_stream_to_file
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.files import get_file_extension, guess_file_extension
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import os, shutil

class CameraPoseEstimatorAction(ComponentAction):
    """Base for camera-pose-estimator driver actions.

    Every request bundles a full image set into a single reconstruction —
    the input array is treated as one scene, not iterated view-by-view.
    A batch or stream of arrays means multiple scenes, each reconstructed
    independently.

    Every driver in this component accepts the same fixed input contract
    (an image array plus a workspace directory), so base owns image
    rendering and workspace routing directly instead of delegating to a
    `_prepare_input` hook.
    """
    def __init__(self, config: CameraPoseEstimatorActionConfig):
        self.config: CameraPoseEstimatorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        images        = await context.render_image_array(self.config.images, single_as_array=True, as_stream=True) if self.config.images is not None else None
        workspace_dir = await context.render_variable(self.config.workspace_dir)
        batch_size    = await context.render_variable(self.config.batch_size)

        primary_input      = images if images is not None else workspace_dir
        is_single_input    = not isinstance(primary_input, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(primary_input, (StreamIterator, AsyncIterator))

        is_single_workspace = not isinstance(workspace_dir, (list, StreamIterator, AsyncIterator))

        params = await self._resolve_params(context)

        if is_single_workspace and images is not None:
            workspace_dir = os.path.join(workspace_dir or os.path.join(".workspace", context.component_id), context.run_id)

        is_direct_output   = not self.config.output or self.config.output == "${result}"
        needs_scene_suffix = is_single_workspace and not is_single_input

        if is_streaming_input:
            async def _stream_output_generator():
                scene_index = 0
                async for batch_images, batch_workspaces in BatchSourceIterator((images, workspace_dir), batch_size=batch_size or 1):
                    if needs_scene_suffix:
                        batch_workspaces = [ f"{workspace}-{scene_index + index}" for index, workspace in enumerate(batch_workspaces) ]
                    batch_inputs = list(zip(batch_images, batch_workspaces))
                    batch_results = await self._estimate_batch(batch_inputs, params, context.cancellation_token)
                    scene_index += len(batch_images)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(primary_input, StreamChunkIterator) and primary_input.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            scene_index = 0
            async for batch_images, batch_workspaces in BatchSourceIterator((images, workspace_dir), batch_size=batch_size or 1):
                if needs_scene_suffix:
                    batch_workspaces = [ f"{workspace}-{scene_index + index}" for index, workspace in enumerate(batch_workspaces) ]
                batch_inputs = list(zip(batch_images, batch_workspaces))
                batch_results = await self._estimate_batch(batch_inputs, params, context.cancellation_token)
                scene_index += len(batch_images)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _estimate_batch(
        self,
        inputs: List[Tuple[Optional[ImageArrayValue], str]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        """Run the driver's SfM pipeline over one batch of scenes.

        Each `inputs[i]` is a `(images, workspace_dir)` tuple describing
        one scene:
          - `images` is a `ImageArrayValue` yielding that scene's image
            stream resources (raw encoded bytes, EXIF preserved), or
            `None` when the driver should reuse images already present
            under `workspace_dir`.
          - `workspace_dir` is the base directory the driver owns for
            this scene — where inputs are read from and intermediate
            plus final artifacts are written. The on-disk layout inside
            it is driver-specific.

        Returns one result dict per scene. Each dict must include a
        `workspace_dir` field pointing at the directory downstream jobs
        should consume (may be a subfolder of the input workspace,
        depending on the driver's output layout).
        """
        pass

    async def _save_images(self, images: ImageArrayValue, images_dir: str) -> None:
        # Wipe stale files from prior runs before writing the new batch.
        if os.path.isdir(images_dir):
            shutil.rmtree(images_dir)

        os.makedirs(images_dir)

        # Write raw encoded bytes to preserve EXIF (a PIL round-trip strips it).
        index = 0
        async for image in images:
            extension  = self._resolve_image_extension(image)
            image_path = os.path.join(images_dir, f"image_{index:04d}.{extension}")
            await save_stream_to_file(image, image_path)
            index += 1

        if index == 0:
            raise ValueError("images array is empty")

    def _resolve_image_extension(self, image: StreamResource) -> str:
        if image.filename:
            extension = get_file_extension(image.filename)

            if extension:
                return extension

        if image.content_type and image.content_type.startswith("image/"):
            extension = guess_file_extension(image.content_type)

            if extension:
                return extension

        return "png"
