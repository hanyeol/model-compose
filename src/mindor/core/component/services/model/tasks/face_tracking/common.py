from __future__ import annotations

from typing import Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import FaceTrackingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.image import ImageValueRenderer
from mindor.core.foundation.variable.time import parse_time
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class FaceTrackingTaskAction(ComponentAction):
    def __init__(self, config: FaceTrackingModelActionConfig):
        self.config: FaceTrackingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        segments = await context.render_variable(self.config.segments)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        prepared_segments = await self._prepare_segments(segments)
        result = await self._track(prepared_segments, params, context.cancellation_token)

        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        similarity_threshold = await context.render_scalar(self.config.params.similarity_threshold, float)
        min_face_size        = await context.render_scalar(self.config.params.min_face_size, int)
        min_appearances      = await context.render_scalar(self.config.params.min_appearances, int)
        merge_gap            = await context.render_scalar(self.config.params.merge_gap, float)
        max_faces_per_frame  = await context.render_scalar(self.config.params.max_faces_per_frame, int)

        return {
            "similarity_threshold": similarity_threshold,
            "min_face_size":        min_face_size,
            "min_appearances":      min_appearances,
            "merge_gap":            merge_gap,
            "max_faces_per_frame":  max_faces_per_frame,
        }

    async def _prepare_segments(self, segments: Any) -> List[Dict[str, Any]]:
        if not isinstance(segments, list):
            raise ValueError("'segments' must be a list of frame segments.")

        renderer = ImageValueRenderer()
        prepared: List[Dict[str, Any]] = []

        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("Each segment must be a mapping with 'frames', 'start_time', and 'end_time' fields.")

            start_time = parse_time(segment["start_time"])
            end_time   = parse_time(segment["end_time"])

            if end_time < start_time:
                raise ValueError(f"segment end_time ({end_time}) must be greater than or equal to start_time ({start_time})")

            rendered = await renderer.render(segment.get("frames"))
            frames = self._normalize_frames(rendered)

            if not frames:
                continue

            prepared.append({
                "frames":     frames,
                "start_time": start_time,
                "end_time":   end_time,
            })

        return prepared

    def _normalize_frames(self, rendered: Any) -> List[PILImage.Image]:
        if rendered is None:
            return []

        if isinstance(rendered, PILImage.Image):
            return [rendered]

        if isinstance(rendered, list):
            return [ frame for frame in rendered if isinstance(frame, PILImage.Image) ]

        return []

    @abstractmethod
    async def _track(
        self,
        segments: List[Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        pass
