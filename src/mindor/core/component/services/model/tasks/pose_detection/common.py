from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import PoseDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class PoseDetectionTaskAction:
    def __init__(self, config: PoseDetectionModelActionConfig):
        self.config: PoseDetectionModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = self._detect(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = self._detect(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_pose_count            = await context.render_variable(self.config.max_pose_count)
        min_confidence            = await context.render_variable(self.config.min_confidence)
        min_presence_confidence   = await context.render_variable(self.config.min_presence_confidence)
        min_tracking_confidence   = await context.render_variable(self.config.min_tracking_confidence)
        return_keypoints          = await context.render_variable(self.config.return_keypoints)
        return_keypoints_3d       = await context.render_variable(self.config.return_keypoints_3d)
        return_openpose_keypoints = await context.render_variable(self.config.return_openpose_keypoints)
        return_segmentation_mask  = await context.render_variable(self.config.return_segmentation_mask)
        return_skeleton_image     = await context.render_variable(self.config.return_skeleton_image)
        skeleton_format           = await context.render_variable(self.config.skeleton_format)

        if str(skeleton_format) not in ("natural", "openpose"):
            raise ValueError(f"'skeleton_format' must be 'natural' or 'openpose', got {str(skeleton_format)!r}")

        if int(max_pose_count) < 1:
            raise ValueError(f"'max_pose_count' must be >= 1, got {int(max_pose_count)}")

        for name, value in [
            ("min_confidence",          float(min_confidence)),
            ("min_presence_confidence", float(min_presence_confidence)),
            ("min_tracking_confidence", float(min_tracking_confidence)),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"'{name}' must be between 0.0 and 1.0, got {value}")

        return {
            "max_pose_count":            int(max_pose_count),
            "min_confidence":            float(min_confidence),
            "min_presence_confidence":   float(min_presence_confidence),
            "min_tracking_confidence":   float(min_tracking_confidence),
            "return_keypoints":          bool(return_keypoints),
            "return_keypoints_3d":       bool(return_keypoints_3d),
            "return_openpose_keypoints": bool(return_openpose_keypoints),
            "return_segmentation_mask":  bool(return_segmentation_mask),
            "return_skeleton_image":     bool(return_skeleton_image),
            "skeleton_format":           str(skeleton_format),
        }

    @abstractmethod
    def _detect(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Dict[str, Any]]:
        pass

class PoseDetectionTaskService(ModelTaskService):
    pass
