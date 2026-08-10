from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, BlazeFaceFaceDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import FaceDetectionTaskAction
from ....base import ComponentActionContext, ModelTaskService
from PIL import Image as PILImage

if TYPE_CHECKING:
    from mediapipe.tasks.python.vision import FaceDetectorResult
    from mediapipe.tasks.python.components.containers import NormalizedKeypoint

class BlazeFaceFaceDetectionTaskAction(FaceDetectionTaskAction):
    def __init__(self, config: BlazeFaceFaceDetectionModelActionConfig, model_path: str):
        super().__init__(config)

        self.model_path: str = model_path

    async def _detect_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _detect() -> List[Dict[str, Any]]:
            from mediapipe import Image as MPImage, ImageFormat
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core.base_options import BaseOptions
            import numpy as np

            options = vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=self.model_path),
                min_detection_confidence=params["min_confidence"],
            )

            results: List[Dict[str, Any]] = []

            with vision.FaceDetector.create_from_options(options) as detector:
                for image in images:
                    rgb_frame = np.asarray(image.convert("RGB"))
                    height, width = rgb_frame.shape[:2]

                    prediction = detector.detect(MPImage(image_format=ImageFormat.SRGB, data=rgb_frame))

                    results.append(self._serialize_detection_result(prediction, width, height, params))

            return results

        return await self._run_in_executor(_detect)

    def _serialize_detection_result(self, prediction: FaceDetectorResult, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        faces: List[Dict[str, Any]] = []

        for detection in prediction.detections:
            face: Dict[str, Any] = {
                "bounding_box": self._serialize_bounding_box(detection.bounding_box, width, height, params["bounding_box_padding"]),
                "score":        float(detection.categories[0].score) if detection.categories else 0.0,
            }

            if params["return_landmarks"] and detection.keypoints:
                face["landmarks"] = self._serialize_landmarks(detection.keypoints, width, height)

            faces.append(face)

        return {
            "faces":  faces,
            "width":  width,
            "height": height,
        }

    @staticmethod
    def _serialize_bounding_box(box: Any, width: int, height: int, padding: float) -> List[int]:
        x = int(box.origin_x)
        y = int(box.origin_y)
        w = int(box.width)
        h = int(box.height)

        if padding > 0.0:
            x -= int(w * padding)
            y -= int(h * padding)
            w += int(w * padding * 2)
            h += int(h * padding * 2)

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(width, x + w)
        y2 = min(height, y + h)

        return [ x1, y1, x2 - x1, y2 - y1 ]

    def _serialize_landmarks(self, keypoints: List[NormalizedKeypoint], width: int, height: int) -> List[Dict[str, int]]:
        landmarks: List[Dict[str, int]] = []

        for keypoint in keypoints:
            landmarks.append({ "x": int(keypoint.x * width), "y": int(keypoint.y * height) })

        return landmarks

class BlazeFaceFaceDetectionTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model_path: Optional[str] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "mediapipe" ]

    async def _load_model(self) -> None:
        self.model_path = await self._provision_model(self.config.model, prefetch=True)

    async def _unload_model(self) -> None:
        self.model_path = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await BlazeFaceFaceDetectionTaskAction(action, self.model_path).run(context)
