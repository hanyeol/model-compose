from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, YoloObjectDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import ObjectDetectionTaskService, ObjectDetectionTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
from pathlib import Path
import asyncio, os

if TYPE_CHECKING:
    from ultralytics import YOLO
    from ultralytics.engine.results import Results
    import numpy as np

_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "ultralytics"

class YoloObjectDetectionTaskAction(ObjectDetectionTaskAction):
    def __init__(self, config: YoloObjectDetectionModelActionConfig, model: YOLO):
        super().__init__(config)

        self.model: YOLO = model

    def _detect(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        classes = self._resolve_class_filter(params["labels"])

        predictions = self.model.predict(
            source=[ image.convert("RGB") for image in images ],
            conf=params["min_confidence"],
            iou=params["iou_threshold"],
            max_det=params["max_object_count"],
            agnostic_nms=params["agnostic_nms"],
            classes=classes,
            verbose=False,
        )

        for image, prediction in zip(images, predictions):
            width, height = image.size
            results.append(self._serialize(prediction, width, height))

        return results

    def _resolve_class_filter(self, labels: Optional[List[str]]) -> Optional[List[int]]:
        if not labels:
            return None

        # Ultralytics exposes model.names as either a dict {id: name} or a list [name, ...]
        if isinstance(self.model.names, dict):
            name_to_id = { name: index for index, name in self.model.names.items() }
        else:
            name_to_id = { name: index for index, name in enumerate(self.model.names) }

        class_ids: List[int] = []

        for label in labels:
            if label not in name_to_id:
                available = sorted(name_to_id.keys())
                raise ValueError(f"Unknown label {label!r}. Available labels: {available}")
            class_ids.append(int(name_to_id[label]))

        return class_ids

    def _serialize(self, prediction: Results, width: int, height: int) -> Dict[str, Any]:
        objects: List[Dict[str, Any]] = []

        if prediction.boxes is not None and len(prediction.boxes) > 0:
            boxes_xyxy = prediction.boxes.xyxy.cpu().numpy()
            boxes_cls  = prediction.boxes.cls.cpu().numpy()
            boxes_conf = prediction.boxes.conf.cpu().numpy()
            names      = prediction.names

            for index in range(boxes_xyxy.shape[0]):
                label_id = int(boxes_cls[index])
                objects.append({
                    "label":        names[label_id] if label_id in names else None,
                    "label_id":     label_id,
                    "score":        float(boxes_conf[index]),
                    "bounding_box": self._serialize_bounding_box(boxes_xyxy[index]),
                })

        return {
            "objects": objects,
            "width":   width,
            "height":  height,
        }

    def _serialize_bounding_box(self, box_xyxy: np.ndarray) -> List[int]:
        x1, y1, x2, y2 = box_xyxy
        return [ int(x1), int(y1), int(x2 - x1), int(y2 - y1) ]

class YoloObjectDetectionTaskService(ObjectDetectionTaskService):
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
        return await self._resolve_local_model(
            cache_dir=_CACHE_DIR,
            label="object detection",
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await YoloObjectDetectionTaskAction(action, self.model).run(context, loop)
