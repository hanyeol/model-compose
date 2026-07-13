from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceEmbeddingModelActionConfig
from mindor.core.logger import logging
from ..common import FaceEmbeddingTaskService, FaceEmbeddingTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os, shutil

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis
    from insightface.app.common import Face
    import numpy as np

class InsightfaceFaceEmbeddingTaskAction(FaceEmbeddingTaskAction):
    config: InsightfaceFaceEmbeddingModelActionConfig

    def __init__(self, config: InsightfaceFaceEmbeddingModelActionConfig, model: FaceAnalysis):
        super().__init__(config, None)

        self.model: FaceAnalysis = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        params["return_landmarks"]  = bool(await context.render_variable(self.config.return_landmarks))
        params["return_gender_age"] = bool(await context.render_variable(self.config.return_gender_age))
        params["max_num_faces"]     = int(await context.render_variable(self.config.max_num_faces))

        return params

    def _embed(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        import numpy as np
        import cv2

        results: List[Dict[str, Any]] = []

        for image in images:
            rgb_frame = np.asarray(image.convert("RGB"))
            height, width = rgb_frame.shape[:2]

            bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
            detections = self.model.get(bgr_frame)

            results.append(self._serialize(detections, width, height, params))

        return results

    def _serialize(self, detections: List[Face], width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        detections = detections[:params["max_num_faces"]] if params["max_num_faces"] and params["max_num_faces"] > 0 else detections
        faces: List[Dict[str, Any]] = []

        for detection in detections:
            embedding = detection.normed_embedding if params["normalize_embeddings"] else detection.embedding

            face: Dict[str, Any] = {
                "embedding":    embedding.tolist(),
                "bounding_box": self._serialize_bounding_box(detection.bbox),
                "score":        float(getattr(detection, "det_score", 0.0)),
            }

            if params["return_landmarks"]:
                landmarks = self._serialize_landmarks(detection)

                if landmarks:
                    face["landmarks"] = landmarks

            if params["return_gender_age"]:
                if getattr(detection, "gender", None) is not None:
                    face["gender"] = self._gender_to_label(int(detection.gender))
                if getattr(detection, "age", None) is not None:
                    face["age"] = int(detection.age)

            pose = getattr(detection, "pose", None)

            if pose is not None:
                face["pose"] = { "pitch": float(pose[0]), "yaw": float(pose[1]), "roll": float(pose[2]) }

            faces.append(face)

        return {
            "faces":  faces,
            "width":  width,
            "height": height,
        }

    def _serialize_landmarks(self, detection: Face) -> List[Dict[str, int]]:
        # Prefer the densest landmark set the loaded model exposes.
        for attr in ("landmark_2d_106", "landmark_3d_68", "kps"):
            points = getattr(detection, attr, None)

            if points is not None:
                return [ { "x": int(p[0]), "y": int(p[1]) } for p in points ]

        return []

    def _serialize_bounding_box(self, bbox: np.ndarray) -> List[int]:
        x1, y1, x2, y2 = [ int(v) for v in bbox ]
        return [ x1, y1, x2 - x1, y2 - y1 ]

    def _gender_to_label(self, gender: int) -> str:
        return "male" if gender == 1 else "female"

class InsightfaceFaceEmbeddingTaskService(FaceEmbeddingTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[FaceAnalysis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "insightface", "opencv-python", "onnxruntime" ]

    async def _load_model(self) -> None:
        self.model = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None

    def _load_pretrained_model(self) -> FaceAnalysis:
        from insightface.app import FaceAnalysis

        params = self._resolve_model_params()

        try:
            model = FaceAnalysis(**params)
        except:
            self._fix_wrong_model_path(params)
            model = FaceAnalysis(**params)

        model.prepare(ctx_id=self._get_device_id())

        return model

    def _resolve_model_params(self) -> Dict[str, Any]:
        if isinstance(self.config.model, (LocalModelConfig, str)):
            if isinstance(self.config.model, LocalModelConfig):
                # TODO: process local storage
                path = self.config.model.path
            else:
                path = self.config.model

            root, name = self._prepare_model_path(path)

            return { "name": name, "root": root }

        raise ValueError(f"Unsupported model type: {type(self.config.model)}")

    def _prepare_model_path(self, path: str) -> Tuple[str, str]:
        root = os.path.dirname(path)
        name = os.path.basename(path)

        if os.path.basename(root) != "models":
            models_dir = os.path.join(root, "models")
            if not os.path.exists(models_dir):
                os.symlink(root, models_dir, target_is_directory=True)
        else:
            root = os.path.dirname(root)

        return (root, name)

    def _fix_wrong_model_path(self, params: Dict[str, Any]) -> None:
        root, name = params["root"], params["name"]
        model_dir = os.path.join(root, "models", name)
        wrong_model_dir = os.path.join(model_dir, name)

        if os.path.isdir(wrong_model_dir):
            for file in os.listdir(wrong_model_dir):
                shutil.move(os.path.join(wrong_model_dir, file), os.path.join(model_dir, file))
            os.rmdir(wrong_model_dir)

    def _get_device_id(self) -> int:
        return 0

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await InsightfaceFaceEmbeddingTaskAction(action, self.model).run(context, loop)
