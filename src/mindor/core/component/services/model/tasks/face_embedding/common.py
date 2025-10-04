from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import FaceEmbeddingModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

class FaceEmbeddingTaskAction:
    def __init__(self, config: FaceEmbeddingModelActionConfig, device: Optional[torch.device]):
        self.config: FaceEmbeddingModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        image = await self._prepare_input(context)
        is_single_input = not isinstance(image, list)
        images: List[PILImage.Image] = [ image ] if is_single_input else image
        results = []

        batch_size = await context.render_variable(self.config.batch_size)
        params     = await self._resolve_embedding_params(context)

        for index in range(0, len(images), batch_size):
            batch_images = images[index:index + batch_size]
            embeddings = await self._embed(batch_images, params)
            results.extend(embeddings)

        return results[0] if is_single_input else results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[PILImage.Image, List[PILImage.Image]]:
        return await context.render_image(self.config.image)

    @abstractmethod
    async def _embed(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[List[float]]:
        pass

    @abstractmethod
    async def _resolve_embedding_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

class FaceEmbeddingTaskService(ModelTaskService):
    pass
