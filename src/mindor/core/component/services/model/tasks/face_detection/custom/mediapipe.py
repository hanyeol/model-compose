from __future__ import annotations

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

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "face_detection" / "mediapipe"

class BlazeFaceFaceDetectionTaskAction(FaceDetectionTaskAction):
    def __init__(self, config: BlazeFaceFaceDetectionModelActionConfig, model_path: str):
        super().__init__(config)

        self.model_path: str = model_path

    async def _detect(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[Dict[str, Any]]:
        return await loop.run_in_executor(None, self._detect_batch, images, params)

    def _detect_batch(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from mediapipe import Image as MPImage, ImageFormat
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        import numpy as np

        include_landmarks: bool = params["include_landmarks"]

        options = vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=self.model_path),
            min_detection_confidence=params["min_confidence"],
        )

        results: List[Dict[str, Any]] = []

        with vision.FaceDetector.create_from_options(options) as detector:
            for image in images:
                rgb_frame = np.asarray(image.convert("RGB"))
                height, width = rgb_frame.shape[:2]

                detection_result = detector.detect(MPImage(image_format=ImageFormat.SRGB, data=rgb_frame))

                detections: List[Dict[str, Any]] = []

                for detection in detection_result.detections:
                    bbox = detection.bounding_box

                    entry: Dict[str, Any] = {
                        "box": [
                            int(bbox.origin_x),
                            int(bbox.origin_y),
                            int(bbox.width),
                            int(bbox.height),
                        ],
                        "score": float(detection.categories[0].score) if detection.categories else 0.0,
                    }

                    if include_landmarks and detection.keypoints:
                        entry["landmarks"] = [
                            { "x": int(kp.x * width), "y": int(kp.y * height) }
                            for kp in detection.keypoints
                        ]

                    detections.append(entry)

                results.append({
                    "detections": detections,
                    "width":      width,
                    "height":     height,
                })

        return results

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
