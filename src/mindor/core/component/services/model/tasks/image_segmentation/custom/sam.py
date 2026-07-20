from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, SamImageSegmentationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import ImageSegmentationTaskService, ImageSegmentationTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
from pathlib import Path
import asyncio, os

if TYPE_CHECKING:
    from ultralytics import SAM
    from ultralytics.engine.results import Results
    import numpy as np

_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "ultralytics"

class SamImageSegmentationTaskAction(ImageSegmentationTaskAction):
    def __init__(self, config: SamImageSegmentationModelActionConfig, model: SAM):
        super().__init__(config)

        self.model: SAM = model

    def _segment(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for image in images:
            rgb_image = image.convert("RGB")
            width, height = rgb_image.size

            if params["box_prompts"] is not None:
                bboxes = [ [ int(x), int(y), int(x + w), int(y + h) ] for x, y, w, h in params["box_prompts"] ]
                predictions = self.model.predict(
                    source=rgb_image,
                    bboxes=bboxes,
                    conf=params["min_confidence"],
                    verbose=False,
                )
                results.append(self._serialize(predictions[0], width, height, params, box_prompted=True))
            else:
                predictions = self.model.predict(
                    source=rgb_image,
                    conf=params["min_confidence"],
                    verbose=False,
                )
                results.append(self._serialize(predictions[0], width, height, params, box_prompted=False))

        return results

    def _serialize(
        self,
        prediction: Results,
        width: int,
        height: int,
        params: Dict[str, Any],
        box_prompted: bool,
    ) -> Dict[str, Any]:
        import numpy as np

        segments: List[Dict[str, Any]] = []

        if prediction.masks is not None and len(prediction.masks) > 0:
            masks_data = prediction.masks.data.cpu().numpy()  # (N, H, W) float or bool
            scores = self._extract_scores(prediction, masks_data.shape[0])

            min_area    = params["min_area"]
            max_count   = params["max_segment_count"]
            return_mask = params["return_mask"]

            for index in range(masks_data.shape[0]):
                mask = masks_data[index] > 0.5
                area = int(mask.sum())

                if min_area is not None and area < min_area:
                    continue

                bounding_box = self._mask_to_bounding_box(mask)

                if bounding_box is None:
                    continue

                segment: Dict[str, Any] = {
                    "score":        float(scores[index]),
                    "bounding_box": bounding_box,
                    "area":         area,
                }

                if return_mask:
                    segment["mask"] = self._mask_to_pil_image(mask)

                if box_prompted:
                    segment["prompt_index"] = index

                segments.append(segment)

            segments.sort(key=lambda item: item["score"], reverse=True)
            segments = segments[:max_count]

        return { "segments": segments, "width": width, "height": height }

    def _extract_scores(self, prediction: Results, count: int) -> List[float]:
        if prediction.boxes is not None and prediction.boxes.conf is not None and len(prediction.boxes.conf) == count:
            return prediction.boxes.conf.cpu().numpy().tolist()

        return [ 1.0 ] * count

    def _mask_to_bounding_box(self, mask: np.ndarray) -> Optional[List[int]]:
        import numpy as np

        rows_any = mask.any(axis=1)
        cols_any = mask.any(axis=0)

        if not rows_any.any() or not cols_any.any():
            return None

        rows = np.where(rows_any)[0]
        cols = np.where(cols_any)[0]
        y1, y2 = int(rows[0]), int(rows[-1])
        x1, x2 = int(cols[0]), int(cols[-1])

        return [ x1, y1, x2 - x1 + 1, y2 - y1 + 1 ]

    def _mask_to_pil_image(self, mask: np.ndarray) -> PILImage.Image:
        return PILImage.fromarray((mask.astype("uint8") * 255), mode="L")

class SamImageSegmentationTaskService(ImageSegmentationTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[SAM] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "ultralytics" ]

    async def _load_model(self) -> None:
        from ultralytics import SAM

        model_path = await self._resolve_model_path()
        self.model = SAM(model_path)

    async def _unload_model(self) -> None:
        self.model = None

    async def _resolve_model_path(self) -> str:
        return await self._resolve_local_model(
            cache_dir=_CACHE_DIR,
            label="image segmentation",
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await SamImageSegmentationTaskAction(action, self.model).run(context, loop)
