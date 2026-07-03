from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from urllib.parse import urlparse
from mindor.dsl.schema.component import ModelComponentConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig, YoloPoseDetectionModelActionConfig
from mindor.core.logger import logging
from mindor.core.foundation.streaming.url import download_to_file
from ..common import PoseDetectionTaskService, PoseDetectionTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os

if TYPE_CHECKING:
    from ultralytics import YOLO

_DEFAULT_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "ultralytics"

class YoloPoseDetectionTaskAction(PoseDetectionTaskAction):
    def __init__(self, config: YoloPoseDetectionModelActionConfig, model: YOLO):
        super().__init__(config)

        self.model: YOLO = model

    async def _detect(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[Dict[str, Any]]:
        return await loop.run_in_executor(None, self._detect_batch, images, params)

    def _detect_batch(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        predictions = self.model.predict(
            source=[ image.convert("RGB") for image in images ],
            conf=params["min_confidence"],
            max_det=params["max_pose_count"],
            verbose=False,
        )

        for image, prediction in zip(images, predictions):
            width, height = image.size
            results.append(self._serialize(prediction, width, height, params))

        return results

    def _serialize(self, prediction: Any, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        poses: List[Dict[str, Any]] = []

        keypoints_tensor = prediction.keypoints  # ultralytics Keypoints
        if keypoints_tensor is None or keypoints_tensor.xy is None:
            return { "poses": poses, "width": width, "height": height }

        keypoints_xy   = keypoints_tensor.xy.cpu().numpy()   # (N, K, 2)
        keypoints_conf = (
            keypoints_tensor.conf.cpu().numpy()              # (N, K)
            if keypoints_tensor.conf is not None
            else None
        )

        for index in range(keypoints_xy.shape[0]):
            entry: Dict[str, Any] = {}

            if params["return_keypoints"]:
                entry["keypoints"] = [
                    {
                        "x":          int(keypoints_xy[index, k, 0]),
                        "y":          int(keypoints_xy[index, k, 1]),
                        "visibility": float(keypoints_conf[index, k]) if keypoints_conf is not None else 1.0,
                    }
                    for k in range(keypoints_xy.shape[1])
                ]

            poses.append(entry)

        return {
            "poses":  poses,
            "width":  width,
            "height": height,
        }

class YoloPoseDetectionTaskService(PoseDetectionTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[YOLO] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "ultralytics" ]

    async def _load_model(self) -> None:
        from ultralytics import YOLO

        model_path = await self._resolve_model_path()
        self.model = YOLO(model_path)

    async def _unload_model(self) -> None:
        self.model = None

    async def _resolve_model_path(self) -> str:
        if isinstance(self.config.model, LocalModelConfig):
            path = self.config.model.path
        elif isinstance(self.config.model, str):
            path = self.config.model
        else:
            raise ValueError(f"Unsupported model config type for yolo pose detection: {type(self.config.model).__name__}")

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
        return await YoloPoseDetectionTaskAction(action, self.model).run(context, loop)
