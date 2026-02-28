from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext

if TYPE_CHECKING:
    import torch

class TextToSpeechTaskAction:
    def __init__(self, config: TextToSpeechModelActionConfig, device: Optional[torch.device]):
        self.config: TextToSpeechModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        text = await self._prepare_input(context)
        is_single_input = not isinstance(text, list)
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        for t in texts:
            audio_bytes = await self._generate(t, context)
            results.append(audio_bytes)

        return results[0] if is_single_input else results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    @abstractmethod
    async def _generate(self, text: str, context: ComponentActionContext) -> bytes:
        pass

class TextToSpeechTaskService(ModelTaskService):
    pass
