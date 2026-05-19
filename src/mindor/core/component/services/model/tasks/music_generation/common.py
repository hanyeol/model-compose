from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext

class MusicGenerationTaskAction:
    def __init__(self, config: MusicGenerationModelActionConfig):
        self.config: MusicGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        prompt = await context.render_variable(self.config.prompt)
        lyrics = await context.render_variable(self.config.lyrics) if self.config.lyrics is not None else None
        params = await self._resolve_generation_params(context)

        return await self._generate(prompt, lyrics, params)

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        duration  = await context.render_variable(self.config.params.duration)
        bpm       = await context.render_variable(self.config.params.bpm)
        key_scale = await context.render_variable(self.config.params.key_scale)

        params: Dict[str, Any] = {
            "duration": duration,
            "bpm": bpm,
            "key_scale": key_scale,
        }

        return params

    @abstractmethod
    async def _generate(self, prompt: str, lyrics: Optional[str], params: Dict[str, Any]) -> bytes:
        pass

class MusicGenerationTaskService(ModelTaskService):
    pass
