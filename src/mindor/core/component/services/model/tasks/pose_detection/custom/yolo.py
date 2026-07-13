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
from ..utils import openpose, coco
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os

if TYPE_CHECKING:
    from ultralytics import YOLO
    from ultralytics.engine.results import Results
    import numpy as np

_DEFAULT_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "ultralytics"

class YoloPoseDetectionTaskAction(PoseDetectionTaskAction):
    def __init__(self, config: YoloPoseDetectionModelActionConfig, model: YOLO):
        super().__init__(config)

        self.model: YOLO = model

    def _detect(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
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

    def _serialize(self, prediction: Results, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        poses: List[Dict[str, Any]] = []

        keypoints_xy   = prediction.keypoints.xy.cpu().numpy()
        keypoints_conf = prediction.keypoints.conf.cpu().numpy() if prediction.keypoints.conf is not None else None
        boxes_xyxy     = prediction.boxes.xyxy.cpu().numpy()
        boxes_conf     = prediction.boxes.conf.cpu().numpy()

        needs_openpose_keypoints = (
            params["return_openpose_keypoints"]
            or (params["return_skeleton_image"] and params["skeleton_format"] == "openpose")
        )
        needs_keypoints = (
            params["return_keypoints"] or needs_openpose_keypoints
            or (params["return_skeleton_image"] and params["skeleton_format"] == "natural")
        )
        min_visibility = params["min_presence_confidence"]

        for index in range(keypoints_xy.shape[0]):
            pose: Dict[str, Any] = {}

            conf_row = keypoints_conf[index] if keypoints_conf is not None else None
            keypoints = self._serialize_keypoints(keypoints_xy[index], conf_row, min_visibility) if needs_keypoints else None
            openpose_keypoints = coco.to_body_18(keypoints) if needs_openpose_keypoints else None

            pose["bounding_box"] = self._serialize_bounding_box(boxes_xyxy[index])
            pose["score"] = float(boxes_conf[index])

            if params["return_keypoints"]:
                pose["keypoints"] = keypoints

            if params["return_openpose_keypoints"]:
                pose["openpose_keypoints"] = openpose_keypoints

            if params["return_skeleton_image"]:
                if params["skeleton_format"] == "openpose":
                    pose["skeleton_image"] = openpose.render_skeleton(openpose_keypoints, width, height)
                else:
                    pose["skeleton_image"] = coco.render_skeleton(keypoints, width, height)

            poses.append(pose)

        return {
            "poses":  poses,
            "width":  width,
            "height": height,
        }

    def _serialize_keypoints(self, keypoints_xy: np.ndarray, keypoints_conf: Optional[np.ndarray], min_visibility: float) -> List[Dict[str, Any]]:
        keypoints: List[Dict[str, Any]] = []

        for k in range(keypoints_xy.shape[0]):
            visibility = float(keypoints_conf[k]) if keypoints_conf is not None else 1.0
            x, y = int(keypoints_xy[k, 0]), int(keypoints_xy[k, 1])

            if visibility < min_visibility or (x == 0 and y == 0):
                keypoints.append({ "x": 0, "y": 0, "visibility": 0.0 })
            else:
                keypoints.append({ "x": x, "y": y, "visibility": visibility })

        return keypoints

    def _serialize_bounding_box(self, box_xyxy: np.ndarray) -> List[int]:
        x1, y1, x2, y2 = box_xyxy
        return [ int(x1), int(y1), int(x2 - x1), int(y2 - y1) ]

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
