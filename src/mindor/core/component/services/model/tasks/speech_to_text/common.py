from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
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
        import numpy as np

        audio = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(audio, list))
        audios: List[np.ndarray] = [ audio ] if is_single_input else audio

        batch_size = await context.render_variable(self.config.batch_size)
        results = []

        for index in range(0, len(audios), batch_size):
            batch_audios = audios[index:index + batch_size]
            transcriptions = await self._transcribe(batch_audios, context)
            results.extend(transcriptions)

        result = results[0] if is_single_input else results
        return await self._render_output(context, result)

    async def _prepare_input(self, context: ComponentActionContext) -> Union[Any, List[Any]]:
        audio = await context.render_variable(self.config.audio)

        if isinstance(audio, list):
            return [ await self._load_audio(a) for a in audio ]

        return await self._load_audio(audio)

    async def _load_audio(self, audio_path: str) -> Any:
        import librosa
        audio_array, _ = librosa.load(audio_path, sr=16000)
        return audio_array

    @abstractmethod
    async def _transcribe(self, audios: List[Any], context: ComponentActionContext) -> List[str]:
        pass

    async def _render_output(self, context: ComponentActionContext, result: Union[str, List[str]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _load_audio_from_path(self, path: str, sample_rate: int = 16000) -> np.ndarray:
        import torchaudio
        import torchaudio.functional as F

        waveform, sr = torchaudio.load(path)

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        if sr != sample_rate:
            waveform = F.resample(waveform, sr, sample_rate)

        return waveform.squeeze(0).numpy()

class SpeechToTextTaskService(ModelTaskService):
    pass
