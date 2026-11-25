from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, BlazeHandHandDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import HandDetectionTaskAction
from ..utils import blazehand, openpose, topology, mask
from ....base import ComponentActionContext, ModelTaskDriver
from PIL import Image as PILImage

if TYPE_CHECKING:
    from mediapipe.tasks.python.vision import HandLandmarkerResult
    from mediapipe.tasks.python.components.containers import NormalizedLandmark

class BlazeHandHandDetectionTaskAction(HandDetectionTaskAction):
    config: BlazeHandHandDetectionModelActionConfig

    def __init__(self, config: BlazeHandHandDetectionModelActionConfig, model_path: str):
        super().__init__(config)

        self.model_path: str = model_path

    async def _detect_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        from mediapipe import Image as MPImage, ImageFormat
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        def _detect() -> List[Dict[str, Any]]:
            import numpy as np

            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=self.model_path),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=params["max_detection_count"],
                min_hand_detection_confidence=params["min_confidence"],
                min_hand_presence_confidence=params["min_presence_confidence"],
                min_tracking_confidence=params["min_tracking_confidence"],
            )

            results: List[Dict[str, Any]] = []

            with vision.HandLandmarker.create_from_options(options) as landmarker:
                for image in images:
                    rgb_frame = np.asarray(image.convert("RGB"))
                    height, width = rgb_frame.shape[:2]

                    prediction = landmarker.detect(MPImage(image_format=ImageFormat.SRGB, data=rgb_frame))
                    results.append(self._serialize_detection_result(prediction, width, height, params))

            return results

        return await self._run_in_executor(_detect)

    def _serialize_detection_result(self, prediction: HandLandmarkerResult, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        # MediaPipe internal field names (hand_landmarks/hand_world_landmarks/handedness) stay inside this method.
        # Outward keys are normalized to keypoints / keypoints_3d / handedness.
        landmarks_lists    = prediction.hand_landmarks or []
        landmarks_3d_lists = prediction.hand_world_landmarks or []
        handedness_lists   = prediction.handedness or []

        hands: List[Dict[str, Any]] = []

        for index, landmarks in enumerate(landmarks_lists):
            hand: Dict[str, Any] = {}

            keypoints = self._serialize_keypoints(landmarks, width, height)
            bounding_box = topology.keypoints_to_bounding_box(keypoints)
            handedness = handedness_lists[index][0] if index < len(handedness_lists) and handedness_lists[index] else None

            hand["handedness"]       = handedness.category_name if handedness else None
            hand["handedness_score"] = float(handedness.score) if handedness else 0.0
            hand["bounding_box"]     = self._serialize_bounding_box(bounding_box, width, height, params["crop_margin_ratio"])

            if params["return_keypoints"]:
                hand["keypoints"] = keypoints

            if params["return_keypoints_3d"] and index < len(landmarks_3d_lists):
                hand["keypoints_3d"] = self._serialize_keypoints_3d(landmarks_3d_lists[index])

            if params["return_segmentation_mask"]:
                hand["segmentation_mask"] = mask.convex_hull_mask(keypoints, width, height)

            if params["return_skeleton_image"]:
                background = params["skeleton_background"]

                if params["skeleton_format"] == "openpose":
                    hand["skeleton_image"] = openpose.render_skeleton(keypoints, width, height, background=background)
                else:
                    hand["skeleton_image"] = blazehand.render_skeleton(keypoints, width, height, background=background)

            hands.append(hand)

        return {
            "hands":  hands,
            "width":  width,
            "height": height,
        }

    def _serialize_keypoints(self, landmarks: List[NormalizedLandmark], width: int, height: int) -> List[Dict[str, Any]]:
        # MediaPipe Hand Landmarker does not populate per-keypoint visibility/presence
        # — all 21 landmarks are regressed even when occluded, so there's no per-point
        # confidence to filter on. Hand-level confidence lives in `handedness_score`.
        return [
            {
                "x": int(landmark.x * width),
                "y": int(landmark.y * height),
                "z": float(landmark.z),
            }
            for landmark in landmarks
        ]

    def _serialize_keypoints_3d(self, landmarks: List[NormalizedLandmark]) -> List[Dict[str, Any]]:
        return [
            {
                "x": float(landmark.x),
                "y": float(landmark.y),
                "z": float(landmark.z),
            }
            for landmark in landmarks
        ]

    @staticmethod
    def _serialize_bounding_box(box: Optional[Dict[str, int]], width: int, height: int, padding: float) -> Optional[Dict[str, int]]:
        if box is None:
            return None

        x, y, w, h = box["x"], box["y"], box["width"], box["height"]

        if padding > 0.0:
            x -= int(w * padding)
            y -= int(h * padding)
            w += int(w * padding * 2)
            h += int(h * padding * 2)

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(width, x + w)
        y2 = min(height, y + h)

        return { "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1 }

class BlazeHandHandDetectionTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model_path: Optional[str] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "mediapipe" ]

    async def _load_model(self) -> None:
        self.model_path = await self._provision_model(self.config.model, prefetch=True)

    async def _unload_model(self) -> None:
        self.model_path = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await BlazeHandHandDetectionTaskAction(action, self.model_path).run(context)
