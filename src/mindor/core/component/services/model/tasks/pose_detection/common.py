from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import PoseDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.logger import logging
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class PoseDetectionTaskAction(ComponentAction):
    def __init__(self, config: PoseDetectionModelActionConfig):
        self.config: PoseDetectionModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._detect_batch(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._detect_batch(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_pose_count            = await context.render_scalar(self.config.max_pose_count, int)
        min_confidence            = await context.render_scalar(self.config.min_confidence, float)
        min_presence_confidence   = await context.render_scalar(self.config.min_presence_confidence, float)
        min_tracking_confidence   = await context.render_scalar(self.config.min_tracking_confidence, float)
        return_keypoints          = await context.render_scalar(self.config.return_keypoints, bool)
        return_keypoints_3d       = await context.render_scalar(self.config.return_keypoints_3d, bool)
        return_openpose_keypoints = await context.render_scalar(self.config.return_openpose_keypoints, bool)
        return_segmentation_mask  = await context.render_scalar(self.config.return_segmentation_mask, bool)
        return_skeleton_image     = await context.render_scalar(self.config.return_skeleton_image, bool)
        skeleton_format           = await context.render_scalar(self.config.skeleton_format, str)

        if skeleton_format not in ("natural", "openpose"):
            raise ValueError(f"'skeleton_format' must be 'natural' or 'openpose', got {skeleton_format!r}")

        if max_pose_count < 1:
            raise ValueError(f"'max_pose_count' must be >= 1, got {max_pose_count}")

        for name, value in [
            ("min_confidence",          min_confidence),
            ("min_presence_confidence", min_presence_confidence),
            ("min_tracking_confidence", min_tracking_confidence),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"'{name}' must be between 0.0 and 1.0, got {value}")

        return {
            "max_pose_count":            max_pose_count,
            "min_confidence":            min_confidence,
            "min_presence_confidence":   min_presence_confidence,
            "min_tracking_confidence":   min_tracking_confidence,
            "return_keypoints":          return_keypoints,
            "return_keypoints_3d":       return_keypoints_3d,
            "return_openpose_keypoints": return_openpose_keypoints,
            "return_segmentation_mask":  return_segmentation_mask,
            "return_skeleton_image":     return_skeleton_image,
            "skeleton_format":           skeleton_format,
        }

    @abstractmethod
    async def _detect_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
