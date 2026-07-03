from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextToImageModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    import torch

class TextToImageTaskAction:
    def __init__(self, config: TextToImageModelActionConfig, device: Optional[torch.device]):
        self.config: TextToImageModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        prompt     = await context.render_variable(self.config.prompt)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(prompt, (list, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(prompt, AsyncIterator):
            async def _stream_output_generator():
                async for batch_prompts in BatchSourceIterator(prompt, batch_size=batch_size or 1):
                    batch_results = await self._generate(batch_prompts, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[PILImage.Image] = []
            async for batch_prompts in BatchSourceIterator(prompt, batch_size=batch_size or 1):
                batch_results = await self._generate(batch_prompts, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _generate(self, prompts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[PILImage.Image]:
        pass

class TextToImageTaskService(ModelTaskService):
    pass
