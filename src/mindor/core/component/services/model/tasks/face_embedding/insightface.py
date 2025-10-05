from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceEmbeddingModelActionConfig
from mindor.core.logger import logging
from .common import FaceEmbeddingTaskService, FaceEmbeddingTaskAction
from ...base import ComponentActionContext
from PIL import Image as PILImage
import asyncio, os, shutil

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis
    from torch import Tensor

class InsightfaceFaceEmbeddingTaskAction(FaceEmbeddingTaskAction):
    def __init__(self, config: InsightfaceFaceEmbeddingModelActionConfig, model: FaceAnalysis):
        super().__init__(config, None)

        self.model: FaceAnalysis = model

    async def _embed(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[List[float]]:
        import numpy as np
        import cv2

        embeddings = []
        for image in images:
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            embeddings.append([ face.embedding.tolist() for face in self.model.get(image_cv) ])

        return embeddings

    async def _resolve_embedding_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

class InsightfaceFaceEmbeddingTaskService(FaceEmbeddingTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[FaceAnalysis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "insightface", "opencv-python", "onnxruntime" ]

    async def _serve(self) -> None:
        try:
            self.model = self._load_pretrained_model()
            logging.info(f"Model loaded successfully: {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

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

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await InsightfaceFaceEmbeddingTaskAction(action, self.model).run(context)
