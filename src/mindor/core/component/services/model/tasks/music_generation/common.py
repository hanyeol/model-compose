from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any, Tuple, Union, List
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext

if TYPE_CHECKING:
    import numpy as np
    import torch

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
    async def _generate(self, prompt: str, lyrics: Optional[str], params: Dict[str, Any]) -> Any:
        pass

    def _encode_samples_to_pcm16(self, samples: Union[torch.Tensor, np.typing.ArrayLike]) -> Tuple[bytes, int]:
        import numpy as np

        if hasattr(samples, "detach"):
            samples = samples.detach()
        if hasattr(samples, "cpu"):
            samples = samples.cpu()
        if hasattr(samples, "numpy"):
            samples = samples.numpy()

        array = np.asarray(samples)
        if array.ndim == 1:
            array = array[:, None]
        elif array.ndim == 2 and array.shape[0] <= 8 and array.shape[0] < array.shape[1]:
            array = array.T
        elif array.ndim != 2:
            raise ValueError(f"Expected mono or stereo audio samples, got shape {array.shape}")

        if np.issubdtype(array.dtype, np.floating):
            array = np.clip(array, -1.0, 1.0)
            array = (array * 32767.0).astype("<i2")
        elif array.dtype != np.int16:
            array = array.astype("<i2")

        return array.tobytes(), int(array.shape[1])

class MusicGenerationTaskService(ModelTaskService):
    pass
