from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from urllib.parse import urlparse
from mindor.dsl.schema.component import ModelComponentConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig, BlazeFaceFaceDetectionModelActionConfig
from mindor.core.logger import logging
from mindor.core.foundation.streaming.url import download_to_file
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

    def _detect(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        if isinstance(self.config.model, LocalModelConfig):
            path = self.config.model.path
        elif isinstance(self.config.model, str):
            path = self.config.model
        else:
            raise ValueError(f"Unsupported model config type for mediapipe face detection: {type(self.config.model).__name__}")

        if path == "__default__":
            return await self._prepare_local_model(_DEFAULT_MODEL_URL)

        return await self._prepare_local_model(path)

    async def _prepare_local_model(self, path_or_url: str) -> str:
        parsed_url = urlparse(path_or_url)

        if parsed_url.scheme in ("", "file"):
            local = parsed_url.path if parsed_url.scheme == "file" else path_or_url
            if not os.path.exists(local):
                raise FileNotFoundError(f"Face detection model not found: {local}")
            return local

        cached = _CACHE_DIR / os.path.basename(parsed_url.path)

        if not cached.exists():
            logging.info("Downloading face detection model: %s", path_or_url)
            await download_to_file(path_or_url, cached)

        return str(cached)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await BlazeFaceFaceDetectionTaskAction(action, self.model_path).run(context, loop)
