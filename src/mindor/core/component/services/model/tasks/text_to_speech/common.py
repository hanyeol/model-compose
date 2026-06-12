from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext

if TYPE_CHECKING:
    import numpy as np
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

        for text in texts:
            audio_bytes = await self._generate(text, context)
            results.append(audio_bytes)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    @abstractmethod
    async def _generate(self, text: str, context: ComponentActionContext) -> Any:
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

class TextToSpeechTaskService(ModelTaskService):
    pass
