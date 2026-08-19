from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceSwapModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..common import FaceSwapTaskAction
from ....base import ComponentActionContext, ModelTaskService
from PIL import Image as PILImage
import os, shutil

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis
    from insightface.app.common import Face
    from insightface.model_zoo.inswapper import INSwapper

class InsightfaceFaceSwapTaskAction(FaceSwapTaskAction):
    config: InsightfaceFaceSwapModelActionConfig

    def __init__(self, config: InsightfaceFaceSwapModelActionConfig, model: INSwapper, detector: FaceAnalysis):
        super().__init__(config)

        self.model: INSwapper = model
        self.detector: FaceAnalysis = detector

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        detection_threshold = await context.render_scalar(self.config.params.detection_threshold, float)
        detection_size      = await context.render_variable(self.config.params.detection_size)

        if not 0.0 <= detection_threshold <= 1.0:
            raise ValueError(f"'detection_threshold' must be between 0.0 and 1.0, got {detection_threshold}")

        if not isinstance(detection_size, (list, tuple)) or len(detection_size) != 2:
            raise ValueError(f"'detection_size' must be a (width, height) pair, got {detection_size!r}")

        params["detection_threshold"] = detection_threshold
        params["detection_size"]      = (int(detection_size[0]), int(detection_size[1]))

        return params

    async def _prepare_source_face(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Face:
        def _prepare_source_face() -> Face:
            import numpy as np
            import cv2

            self.detector.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])

            image_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
            faces = self.detector.get(image_cv)

            if not faces:
                raise ValueError("No face detected in the source image.")

            return max(faces, key=lambda face: face.det_score)

        return await self._run_in_executor(_prepare_source_face)

    async def _swap_batch(
        self,
        images: List[PILImage.Image],
        source_face: Face,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _swap() -> List[PILImage.Image]:
            import numpy as np
            import cv2

            self.detector.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])

            results: List[PILImage.Image] = []

            for image in images:
                image_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
                target_faces = self.detector.get(image_cv)

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
                    swapped = self.model.get(swapped, target_face, source_face, paste_back=True)

                results.append(PILImage.fromarray(cv2.cvtColor(swapped, cv2.COLOR_BGR2RGB)))

            return results

        return await self._run_in_executor(_swap)

class InsightfaceFaceSwapTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[INSwapper] = None
        self.detector: Optional[FaceAnalysis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "insightface", "opencv-python", "onnxruntime" ]

    async def _load_model(self) -> None:
        model, detector = await self._load_pretrained_model()

        self.model    = model
        self.detector = detector

    async def _unload_model(self) -> None:
        self.model    = None
        self.detector = None

    async def _load_pretrained_model(self) -> Tuple[INSwapper, FaceAnalysis]:
        from insightface.app import FaceAnalysis
        from insightface.model_zoo import get_model

        root, name = await self._provision_model(self.config.model, prefetch=True)
        providers = self._resolve_onnx_providers()
        model = get_model(os.path.join(root, name), download=False, download_zip=False)
        detector = FaceAnalysis(name=self.config.detector_model, root=root, providers=providers)
        detector.prepare(ctx_id=self._get_device_id(), det_size=(640, 640))

        logging.debug(f"InsightFace providers: {providers}")

        return model, detector

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

    def _get_device_id(self) -> int:
        return 0

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await InsightfaceFaceSwapTaskAction(action, self.model, self.detector).run(context)
