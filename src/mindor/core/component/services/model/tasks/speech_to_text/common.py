from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from mindor.core.utils.audio import create_audio_source, load_audio_array
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

class SpeechToTextTaskAction:
    def __init__(self, config: SpeechToTextModelActionConfig, device: Optional[torch.device]):
        self.config: SpeechToTextModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(audio, list))
        audios: List[Tuple[np.ndarray, int]] = [ audio ] if is_single_input else audio

        batch_size = await context.render_variable(self.config.batch_size)
        results = []

        for index in range(0, len(audios), batch_size):
            batch = audios[index:index + batch_size]
            transcriptions = await self._transcribe(batch, context)
            results.extend(transcriptions)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Union[Tuple[Any, int], List[Tuple[Any, int]]]:
        value = await context.render_variable(self.config.audio)

        if isinstance(value, list):
            return [ await load_audio_array(create_audio_source(v)) for v in value ]

        return await load_audio_array(create_audio_source(value))

    @abstractmethod
    async def _transcribe(self, audios: List[Tuple[Any, int]], context: ComponentActionContext) -> List[str]:
        pass

class SpeechToTextTaskService(ModelTaskService):
    pass
