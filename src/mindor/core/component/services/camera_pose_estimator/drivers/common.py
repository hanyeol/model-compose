from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import CameraPoseEstimatorActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import os

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
    def __init__(self, config: CameraPoseEstimatorActionConfig, context: ComponentActionContext):
        self.config: CameraPoseEstimatorActionConfig = config
        self.context: ComponentActionContext = context

    async def run(self) -> Any:
        images        = await self.context.render_image_array(self.config.images, single_as_array=True) if self.config.images is not None else None
        workspace_dir = await self.context.render_variable(self.config.workspace_dir)
        batch_size    = await self.context.render_variable(self.config.batch_size)

        if images is not None:
            is_single_input    = not isinstance(images, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(images, (StreamIterator, AsyncIterator))
        else:
            is_single_input    = not isinstance(workspace_dir, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(workspace_dir, (StreamIterator, AsyncIterator))

        is_single_workspace = not isinstance(workspace_dir, (list, StreamIterator, AsyncIterator))

        params = await self._resolve_params()

        if is_single_workspace and images is not None:
            workspace_dir = os.path.join(workspace_dir or os.path.join(".workspace", self.context.component_id), self.context.run_id)

        is_direct_output   = not self.config.output or self.config.output == "${result}"
        needs_scene_suffix = is_single_workspace and not is_single_input

        if is_streaming_input:
            async def _stream_output_generator():
                scene_index = 0
                async for batch_images, batch_workspaces in BatchSourceIterator((images, workspace_dir), batch_size=batch_size or 1):
                    if needs_scene_suffix:
                        batch_workspaces = [ f"{workspace}-{scene_index + index}" for index, workspace in enumerate(batch_workspaces) ]
                    batch_inputs = list(zip(batch_images, batch_workspaces))
                    batch_results = await self._estimate_batch(batch_inputs, params, self.context.cancellation_token)
                    scene_index += len(batch_images)
                    for result in batch_results:
                        self.context.register_source("result[]", result)
                        yield (await self.context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            scene_index = 0
            async for batch_images, batch_workspaces in BatchSourceIterator((images, workspace_dir), batch_size=batch_size or 1):
                if needs_scene_suffix:
                    batch_workspaces = [ f"{workspace}-{scene_index + index}" for index, workspace in enumerate(batch_workspaces) ]
                batch_inputs = list(zip(batch_images, batch_workspaces))
                batch_results = await self._estimate_batch(batch_inputs, params, self.context.cancellation_token)
                scene_index += len(batch_images)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            self.context.register_source("result", result)

            return (await self.context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self) -> Dict[str, Any]:
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
          - `images` is an `ImageArrayValue` holding that scene's images,
            or `None` when the driver should reuse images already
            present under `workspace_dir`.
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
