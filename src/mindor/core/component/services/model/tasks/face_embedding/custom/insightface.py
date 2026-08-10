from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceEmbeddingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..common import FaceEmbeddingTaskAction, FaceEmbedding
from ....base import ComponentActionContext, ModelTaskService
from PIL import Image as PILImage
import os, shutil

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis
    from insightface.app.common import Face
    import numpy as np

class InsightfaceFaceEmbeddingTaskAction(FaceEmbeddingTaskAction):
    config: InsightfaceFaceEmbeddingModelActionConfig

    def __init__(self, config: InsightfaceFaceEmbeddingModelActionConfig, model: FaceAnalysis):
        super().__init__(config, None)

        self.model: FaceAnalysis = model
        self._prepared: bool = False

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        return_landmarks    = await context.render_scalar(self.config.return_landmarks, bool)
        return_gender_age   = await context.render_scalar(self.config.return_gender_age, bool)
        detection_threshold = await context.render_scalar(self.config.params.detection_threshold, float)
        max_num_faces       = await context.render_scalar(self.config.params.max_num_faces, int)

        if not 0.0 <= detection_threshold <= 1.0:
            raise ValueError(f"'detection_threshold' must be between 0.0 and 1.0, got {detection_threshold}")

        params["return_landmarks"]    = return_landmarks
        params["return_gender_age"]   = return_gender_age
        params["detection_threshold"] = detection_threshold
        params["detection_size"]      = tuple(self.config.params.detection_size)
        params["max_num_faces"]       = max_num_faces

        return params

    async def _embed_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _embed() -> List[Dict[str, Any]]:
            import numpy as np
            import cv2

            if not self._prepared:
                self.model.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])
                self._prepared = True

            max_num = params["max_num_faces"] if params["max_num_faces"] and params["max_num_faces"] > 0 else 0
            results: List[Dict[str, Any]] = []

            for image in images:
                rgb_frame = np.asarray(image.convert("RGB"))
                height, width = rgb_frame.shape[:2]

                bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                detections = self.model.get(bgr_frame, max_num=max_num)

                results.append(self._serialize_embedding_result(detections, width, height, params))

            return results

        return await self._run_in_executor(_embed)

    def _serialize_embedding_result(self, detections: List[Face], width: int, height: int, params: Dict[str, Any]) -> Dict[str, Any]:
        min_face_size = params["min_face_size"] or 0
        faces: List[Dict[str, Any]] = []

        for detection in detections:
            bounding_box = self._serialize_bounding_box(detection.bbox)

            if min_face_size > 0 and min(bounding_box[2], bounding_box[3]) < min_face_size:
                continue

            embedding = detection.normed_embedding if params["normalize_embeddings"] else detection.embedding

            face: Dict[str, Any] = {
                "embedding":    FaceEmbedding(embedding.tolist()),
                "bounding_box": bounding_box,
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

class InsightfaceFaceEmbeddingTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[FaceAnalysis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "insightface", "opencv-python", "onnxruntime" ]

    async def _load_model(self) -> None:
        self.model = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None

    async def _load_pretrained_model(self) -> FaceAnalysis:
        from insightface.app import FaceAnalysis

        root, name = await self._provision_model(self.config.model, prefetch=True)
        providers = self._resolve_onnx_providers()

        logging.debug(f"InsightFace providers: {providers}")

        model = FaceAnalysis(name=name, root=root, providers=providers)
        model.prepare(ctx_id=self._get_device_id())

        return model

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> Tuple[str, str]:
        path = await super()._provision_model(model, prefetch=prefetch)

        # `FaceAnalysis(name=X, root=R)` expects the pack at `R/models/X/*.onnx`.
        # Reconcile whatever the generic provisioner produced with that layout:
        #   1. Flatten `path/name/` archive nesting if present.
        #   2. Ensure a `models` directory (or symlink) sits alongside the pack.
        name = os.path.basename(path)
        self._flatten_nested_pack(path, name)

        root = os.path.dirname(path)
        self._ensure_models_dir(root)

        # If the pack already lives under a real `models/` directory (e.g. the
        # user pointed `path` at `.../models/antelopev2`), step one level up so
        # `root` names the parent, not the `models` dir itself.
        if os.path.basename(root) == "models" and not os.path.islink(root):
            root = os.path.dirname(root)

        return (root, name)

    @staticmethod
    def _resolve_onnx_providers() -> List[str]:
        """Prefer hardware-accelerated onnxruntime providers over CPU. InsightFace's
        default is `[CUDA, CPU]`, so on Apple Silicon it silently falls back to CPU
        and per-frame detection can take seconds. Adding CoreML (Apple), then any
        available GPU providers ahead of CPU restores hardware acceleration."""
        import onnxruntime as ort

        available = set(ort.get_available_providers())
        preferred = [
            "CUDAExecutionProvider",
            "TensorrtExecutionProvider",
            "ROCMExecutionProvider",
            "CoreMLExecutionProvider",
            "DmlExecutionProvider",
        ]
        providers = [ provider for provider in preferred if provider in available ]
        providers.append("CPUExecutionProvider")

        return providers

    @staticmethod
    def _flatten_nested_pack(path: str, name: str) -> None:
        """Some InsightFace archives (e.g. antelopev2.zip) wrap the model files
        in a top-level directory that matches the pack name, so extraction into
        `path/` yields `path/name/*.onnx` instead of `path/*.onnx`. Move the
        files up one level so the layout matches what `FaceAnalysis` expects."""
        nested = os.path.join(path, name)

        if not os.path.isdir(nested):
            return

        for entry in os.listdir(nested):
            src = os.path.join(nested, entry)
            dst = os.path.join(path, entry)
            if os.path.exists(dst):
                continue
            shutil.move(src, dst)

        if not os.listdir(nested):
            os.rmdir(nested)

    @staticmethod
    def _ensure_models_dir(root: str) -> None:
        """`FaceAnalysis` resolves models under `root/models/`. If the caller's
        `root` doesn't already end in `models`, plant a symlink so both layouts
        work. Recreate the link if it's dangling or points somewhere unexpected
        so re-runs after a failed provisioning don't get stuck."""
        if os.path.basename(root) == "models":
            return

        link_path = os.path.join(root, "models")
        target = os.path.abspath(root)

        if os.path.islink(link_path):
            if os.path.realpath(link_path) == target:
                return
            os.unlink(link_path)
        elif os.path.exists(link_path):
            return

        os.symlink(target, link_path, target_is_directory=True)

    def _get_device_id(self) -> int:
        return 0

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await InsightfaceFaceEmbeddingTaskAction(action, self.model).run(context)
