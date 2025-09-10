from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import ImageGenerationModelActionConfig, ColorFormat
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

class ImageGenerationTaskAction:
    def __init__(self, config: ImageGenerationModelActionConfig, device: torch.device):
        self.config: ImageGenerationModelActionConfig = config
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext) -> Any:
        text = await self._prepare_input(context)
        is_single_input = not isinstance(text, list)
        texts: List[PILImage.Image] = [ text ] if is_single_input else text
        results = []

        batch_size   = await context.render_variable(self.config.batch_size)
        params       = await self._resolve_generation_params(context)

        for index in range(0, len(texts), batch_size):
            batch_texts = texts[index:index + batch_size]
            upscaled_images = await self._upscale(batch_texts, params)
            results.extend(upscaled_images)

        return results[0] if is_single_input else results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_image(self.config.image)

    @abstractmethod
    async def _generate(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        pass

    @abstractmethod
    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

class ImageGenerationTaskService(ModelTaskService):
    pass
