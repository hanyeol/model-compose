from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, BlazeFaceFaceDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import FaceDetectionTaskService, FaceDetectionTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os

if TYPE_CHECKING:
    from mediapipe.tasks.python.vision import FaceDetectorResult
    from mediapipe.tasks.python.components.containers import NormalizedKeypoint

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "mediapipe"

class BlazeFaceFaceDetectionTaskAction(FaceDetectionTaskAction):
    def __init__(self, config: BlazeFaceFaceDetectionModelActionConfig, model_path: str):
        super().__init__(config)

        self.model_path: str = model_path

    def _detect(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Dict[str, Any]]:
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

                results.append(self._serialize(prediction, width, height, params))

        return results

    def _serialize(self, prediction: FaceDetectorResult, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        faces: List[Dict[str, Any]] = []

        for detection in prediction.detections:
            face: Dict[str, Any] = {
                "bounding_box": [
                    int(detection.bounding_box.origin_x),
                    int(detection.bounding_box.origin_y),
                    int(detection.bounding_box.width),
                    int(detection.bounding_box.height),
                ],
                "score": float(detection.categories[0].score) if detection.categories else 0.0,
            }

            if params["return_landmarks"] and detection.keypoints:
                face["landmarks"] = self._serialize_landmarks(detection.keypoints, width, height)

            faces.append(face)

        return {
            "faces":  faces,
            "width":  width,
            "height": height,
        }

    def _serialize_landmarks(self, keypoints: List[NormalizedKeypoint], width: int, height: int) -> List[Dict[str, int]]:
        landmarks: List[Dict[str, int]] = []

        for keypoint in keypoints:
            landmarks.append({ "x": int(keypoint.x * width), "y": int(keypoint.y * height) })

        return landmarks

class BlazeFaceFaceDetectionTaskService(FaceDetectionTaskService):
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
            label="face detection",
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await BlazeFaceFaceDetectionTaskAction(action, self.model_path).run(context, loop)
