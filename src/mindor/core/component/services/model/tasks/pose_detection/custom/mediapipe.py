from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, BlazePosePoseDetectionModelActionConfig
from ..common import PoseDetectionTaskService, PoseDetectionTaskAction
from ..utils import openpose, blazepose, topology
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os

if TYPE_CHECKING:
    from mediapipe.tasks.python.vision import PoseLandmarkerResult
    from mediapipe.tasks.python.components.containers import NormalizedLandmark
    from mediapipe import Image as MPImage

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "mediapipe"

class BlazePosePoseDetectionTaskAction(PoseDetectionTaskAction):
    def __init__(self, config: BlazePosePoseDetectionModelActionConfig, model_path: str):
        super().__init__(config)

        self.model_path: str = model_path

    def _detect(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
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

                prediction = landmarker.detect(MPImage(image_format=ImageFormat.SRGB, data=rgb_frame))

                results.append(self._serialize(prediction, width, height, params))

        return results

    def _serialize(self, prediction: PoseLandmarkerResult, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        # MediaPipe internal field names (pose_landmarks/pose_world_landmarks) stay inside this method.
        # Outward keys are normalized to keypoints / keypoints_3d.
        poses: List[Dict[str, Any]] = []
        landmarks_lists    = prediction.pose_landmarks or []
        landmarks_3d_lists = prediction.pose_world_landmarks or []
        segmentation_masks = prediction.segmentation_masks or []

        needs_openpose_keypoints = (
            params["return_openpose_keypoints"]
            or (params["return_skeleton_image"] and params["skeleton_format"] == "openpose")
        )
        min_visibility = params["min_presence_confidence"]

        for index, landmarks in enumerate(landmarks_lists):
            pose: Dict[str, Any] = {}

            keypoints = self._serialize_keypoints(landmarks, width, height, min_visibility)
            openpose_keypoints = blazepose.to_body_18(keypoints) if needs_openpose_keypoints else None

            pose["bounding_box"] = topology.keypoints_to_bounding_box(keypoints)

            if params["return_keypoints"]:
                pose["keypoints"] = keypoints

            if params["return_keypoints_3d"]:
                pose["keypoints_3d"] = self._serialize_keypoints_3d(landmarks_3d_lists[index])

            if params["return_openpose_keypoints"]:
                pose["openpose_keypoints"] = openpose_keypoints

            if params["return_segmentation_mask"]:
                pose["segmentation_mask"] = self._to_pil_image(segmentation_masks[index])

            if params["return_skeleton_image"]:
                if params["skeleton_format"] == "openpose":
                    pose["skeleton_image"] = openpose.render_skeleton(openpose_keypoints, width, height)
                else:
                    pose["skeleton_image"] = blazepose.render_skeleton(keypoints, width, height)

            poses.append(pose)

        return {
            "poses":  poses,
            "width":  width,
            "height": height,
        }

    def _serialize_keypoints(self, landmarks: List[NormalizedLandmark], width: int, height: int, min_visibility: float) -> List[Dict[str, Any]]:
        keypoints: List[Dict[str, Any]] = []

        for landmark in landmarks:
            visibility = float(landmark.visibility)
            presence   = float(landmark.presence)
            hidden = visibility < min_visibility or presence < min_visibility
            keypoints.append({
                "x":          0 if hidden else int(landmark.x * width),
                "y":          0 if hidden else int(landmark.y * height),
                "z":          float(landmark.z),
                "visibility": 0.0 if hidden else visibility,
                "presence":   presence,
            })

        return keypoints

    def _serialize_keypoints_3d(self, landmarks: List[NormalizedLandmark]) -> List[Dict[str, Any]]:
        return [
            {
                "x":          float(landmark.x),
                "y":          float(landmark.y),
                "z":          float(landmark.z),
                "visibility": float(landmark.visibility),
                "presence":   float(landmark.presence),
            }
            for landmark in landmarks
        ]

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
        return await self._resolve_local_model(
            cache_dir=_CACHE_DIR,
            default_url=_DEFAULT_MODEL_URL,
            label="pose detection",
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await BlazePosePoseDetectionTaskAction(action, self.model_path).run(context, loop)
