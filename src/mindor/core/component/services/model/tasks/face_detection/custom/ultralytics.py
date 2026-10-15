from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, YoloFaceDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import FaceDetectionTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch
    from ultralytics import YOLO

class YoloFaceDetectionTaskAction(FaceDetectionTaskAction):
    config: YoloFaceDetectionModelActionConfig

    def __init__(self, config: YoloFaceDetectionModelActionConfig, model: YOLO, device: torch.device):
        super().__init__(config)

        self.model: YOLO = model
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        detection_size = await context.render_scalar(self.config.params.detection_size, int)
        iou_threshold  = await context.render_scalar(self.config.params.iou_threshold, float)
        max_num_faces  = await context.render_scalar(self.config.params.max_num_faces, int)

        if detection_size <= 0:
            raise ValueError(f"'detection_size' must be > 0, got {detection_size}")

        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError(f"'iou_threshold' must be between 0.0 and 1.0, got {iou_threshold}")

        params.update({
            "detection_size": detection_size,
            "iou_threshold":  iou_threshold,
            "max_num_faces":  max_num_faces,
        })

        return params

    async def _detect_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _detect() -> List[Dict[str, Any]]:
            max_det = params["max_num_faces"] if params["max_num_faces"] and params["max_num_faces"] > 0 else 300

            predictions = self.model.predict(
                source=[ image.convert("RGB") for image in images ],
                imgsz=params["detection_size"],
                conf=params["min_confidence"],
                iou=params["iou_threshold"],
                max_det=max_det,
                device=str(self.device),
                verbose=False,
            )

            results: List[Dict[str, Any]] = []

            for image, prediction in zip(images, predictions):
                width, height = image.size
                results.append(self._serialize_detection_result(prediction, width, height, params))

            return results

        return await self._run_in_executor(_detect)

    def _serialize_detection_result(self, prediction: Any, width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        faces: List[Dict[str, Any]] = []

        boxes = prediction.boxes

        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.cpu().tolist()
            scores = boxes.conf.cpu().tolist()

            for (x1, y1, x2, y2), score in zip(xyxy, scores):
                faces.append({
                    "bounding_box": self._serialize_bounding_box(x1, y1, x2, y2, width, height, params["bounding_box_padding"]),
                    "score":        float(score),
                })

        return {
            "faces":  faces,
            "width":  width,
            "height": height,
        }

    @staticmethod
    def _serialize_bounding_box(x1: float, y1: float, x2: float, y2: float, width: int, height: int, padding: float) -> Dict[str, int]:
        x = int(x1)
        y = int(y1)
        w = int(x2 - x1)
        h = int(y2 - y1)

        if padding > 0.0:
            x -= int(w * padding)
            y -= int(h * padding)
            w += int(w * padding * 2)
            h += int(h * padding * 2)

        cx1 = max(0, x)
        cy1 = max(0, y)
        cx2 = min(width,  x + w)
        cy2 = min(height, y + h)

        return { "x": cx1, "y": cy1, "width": cx2 - cx1, "height": cy2 - cy1 }

class YoloFaceDetectionTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[YOLO] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "ultralytics" ]

    async def _load_model(self) -> None:
        from ultralytics import YOLO

        model_path = await self._provision_model(self.config.model, prefetch=True)
        self.device = self._resolve_device(self.config.device)

        def _load() -> YOLO:
            model = YOLO(model_path)
            model.to(self.device)

            return model

        self.model = await self._run_in_executor(_load)

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await YoloFaceDetectionTaskAction(action, self.model, self.device).run(context)
