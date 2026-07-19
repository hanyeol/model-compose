from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceSwapModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..common import FaceSwapTaskService, FaceSwapTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis
    from insightface.app.common import Face
    from insightface.model_zoo.inswapper import INSwapper

_DEFAULT_SWAPPER_URL = "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx"
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "models" / "insightface"

class InsightfaceFaceSwapTaskAction(FaceSwapTaskAction):
    config: InsightfaceFaceSwapModelActionConfig

    def __init__(self, config: InsightfaceFaceSwapModelActionConfig, analyzer: FaceAnalysis, swapper: INSwapper):
        super().__init__(config)

        self.analyzer: FaceAnalysis = analyzer
        self.swapper: INSwapper = swapper

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        detection_threshold = await context.render_variable(self.config.detection_threshold)
        if not 0.0 <= float(detection_threshold) <= 1.0:
            raise ValueError(f"'detection_threshold' must be between 0.0 and 1.0, got {float(detection_threshold)}")

        params["detection_threshold"] = float(detection_threshold)
        params["detection_size"]      = tuple(self.config.detection_size)

        return params

    def _prepare_source_face(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Face:
        import numpy as np
        import cv2

        self.analyzer.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])

        image_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        faces = self.analyzer.get(image_cv)

        if not faces:
            raise ValueError("No face detected in the source image.")

        return max(faces, key=lambda face: face.det_score)

    def _swap(
        self,
        images: List[PILImage.Image],
        source_face: Face,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[PILImage.Image]:
        import numpy as np
        import cv2

        self.analyzer.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])

        results: List[PILImage.Image] = []

        for image in images:
            image_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
            target_faces = self.analyzer.get(image_cv)

            if not target_faces:
                results.append(image)
                continue

            target_faces.sort(key=lambda face: face.det_score, reverse=True)

            if params["swap_all_faces"]:
                selected_faces = target_faces
            else:
                if params["face_index"] >= len(target_faces):
                    results.append(image)
                    continue
                selected_faces = [ target_faces[params["face_index"]] ]

            swapped = image_cv
            for target_face in selected_faces:
                swapped = self.swapper.get(swapped, target_face, source_face, paste_back=True)

            results.append(PILImage.fromarray(cv2.cvtColor(swapped, cv2.COLOR_BGR2RGB)))

        return results

class InsightfaceFaceSwapTaskService(FaceSwapTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.analyzer: Optional[FaceAnalysis] = None
        self.swapper: Optional[INSwapper] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "insightface", "opencv-python", "onnxruntime" ]

    async def _load_model(self) -> None:
        swapper_path = await self._resolve_swapper_path()
        self.analyzer = self._load_analyzer()
        self.swapper = self._load_swapper(swapper_path)

    async def _unload_model(self) -> None:
        self.analyzer = None
        self.swapper = None

    def _load_analyzer(self) -> FaceAnalysis:
        from insightface.app import FaceAnalysis

        detector_root = str(_CACHE_DIR)
        os.makedirs(os.path.join(detector_root, "models"), exist_ok=True)

        analyzer = FaceAnalysis(name=self.config.detector_model, root=detector_root)
        analyzer.prepare(ctx_id=0, det_size=(640, 640))
        return analyzer

    def _load_swapper(self, swapper_path: str) -> INSwapper:
        from insightface.model_zoo import get_model

        return get_model(swapper_path, download=False, download_zip=False)

    async def _resolve_swapper_path(self) -> str:
        return await self._resolve_local_model(
            cache_dir=_CACHE_DIR,
            default_url=_DEFAULT_SWAPPER_URL,
            label="face swap",
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await InsightfaceFaceSwapTaskAction(action, self.analyzer, self.swapper).run(context, loop)
