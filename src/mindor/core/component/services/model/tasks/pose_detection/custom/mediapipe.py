from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from urllib.parse import urlparse
from mindor.dsl.schema.component import ModelComponentConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig, BlazePosePoseDetectionModelActionConfig
from mindor.core.logger import logging
from mindor.core.foundation.streaming.url import download_to_file
from ..common import PoseDetectionTaskService, PoseDetectionTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os

if TYPE_CHECKING:
    from mediapipe import Image as MPImage

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "mediapipe"

class BlazePosePoseDetectionTaskAction(PoseDetectionTaskAction):
    def __init__(self, config: BlazePosePoseDetectionModelActionConfig, model_path: str):
        super().__init__(config)

        self.model_path: str = model_path

    async def _detect(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[Dict[str, Any]]:
        return await loop.run_in_executor(None, self._detect_batch, images, params)

    def _detect_batch(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from mediapipe import Image as MPImage, ImageFormat
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        import numpy as np

        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self.model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=params["max_pose_count"],
            min_pose_detection_confidence=params["min_confidence"],
            min_pose_presence_confidence=params["min_presence_confidence"],
            min_tracking_confidence=params["min_tracking_confidence"],
            output_segmentation_masks=params["return_segmentation_mask"],
        )

        results: List[Dict[str, Any]] = []

        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            for image in images:
                rgb_frame = np.asarray(image.convert("RGB"))
                height, width = rgb_frame.shape[:2]

                detection_result = landmarker.detect(MPImage(image_format=ImageFormat.SRGB, data=rgb_frame))

                results.append(self._serialize(detection_result, width, height, params))

        return results

    def _serialize(self, detection_result: Any, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        # MediaPipe internal field names (pose_landmarks/pose_world_landmarks) stay inside this method.
        # Outward keys are normalized to keypoints / keypoints_3d.
        poses: List[Dict[str, Any]] = []
        keypoints_lists       = detection_result.pose_landmarks or []
        keypoints_3d_lists    = detection_result.pose_world_landmarks or []
        segmentation_masks    = detection_result.segmentation_masks or []

        for index, keypoints in enumerate(keypoints_lists):
            entry: Dict[str, Any] = {}

            if params["return_keypoints"]:
                entry["keypoints"] = [
                    {
                        "x":          int(keypoint.x * width),
                        "y":          int(keypoint.y * height),
                        "z":          float(keypoint.z),
                        "visibility": float(keypoint.visibility),
                        "presence":   float(keypoint.presence),
                    }
                    for keypoint in keypoints
                ]

            if params["return_keypoints_3d"] and index < len(keypoints_3d_lists):
                entry["keypoints_3d"] = [
                    {
                        "x":          float(keypoint.x),
                        "y":          float(keypoint.y),
                        "z":          float(keypoint.z),
                        "visibility": float(keypoint.visibility),
                        "presence":   float(keypoint.presence),
                    }
                    for keypoint in keypoints_3d_lists[index]
                ]

            if params["return_segmentation_mask"] and index < len(segmentation_masks):
                entry["segmentation_mask"] = self._to_pil_image(segmentation_masks[index])

            poses.append(entry)

        return {
            "poses":  poses,
            "width":  width,
            "height": height,
        }

    def _to_pil_image(self, image: MPImage) -> PILImage.Image:
        import numpy as np

        # MediaPipe returns either H×W or H×W×1 depending on version; collapse to 2D.
        array = np.squeeze(image.numpy_view())  # float32 [0, 1]
        return PILImage.fromarray((array * 255).astype(np.uint8), mode="L")

class BlazePosePoseDetectionTaskService(PoseDetectionTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model_path: Optional[str] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "mediapipe" ]

    async def _load_model(self) -> None:
        self.model_path = await self._resolve_model_path()

    async def _unload_model(self) -> None:
        self.model_path = None

    async def _resolve_model_path(self) -> str:
        if isinstance(self.config.model, LocalModelConfig):
            path = self.config.model.path
        elif isinstance(self.config.model, str):
            path = self.config.model
        else:
            raise ValueError(f"Unsupported model config type for mediapipe pose detection: {type(self.config.model).__name__}")

        if path == "__default__":
            return await self._prepare_local_model(_DEFAULT_MODEL_URL)

        return await self._prepare_local_model(path)

    async def _prepare_local_model(self, path_or_url: str) -> str:
        parsed_url = urlparse(path_or_url)

        if parsed_url.scheme in ("", "file"):
            local = parsed_url.path if parsed_url.scheme == "file" else path_or_url
            if not os.path.exists(local):
                raise FileNotFoundError(f"Pose detection model not found: {local}")
            return local

        cached = _CACHE_DIR / os.path.basename(parsed_url.path)

        if not cached.exists():
            logging.info("Downloading pose detection model: %s", path_or_url)
            await download_to_file(path_or_url, cached)

        return str(cached)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await BlazePosePoseDetectionTaskAction(action, self.model_path).run(context, loop)
