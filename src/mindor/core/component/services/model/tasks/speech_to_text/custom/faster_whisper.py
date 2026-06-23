from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, FasterWhisperSpeechToTextModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, SpeechToTextModelActionConfig
from mindor.core.utils.streaming.audio import load_audio_array
from mindor.core.utils.streaming.media import MediaSource
from ......base import ComponentActionContext
from ..common import SpeechToTextTaskService, SpeechToTextTaskAction
import asyncio

if TYPE_CHECKING:
    from faster_whisper import WhisperModel
    import numpy as np
    import torch

class FasterWhisperSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: SpeechToTextModelActionConfig,
        model: WhisperModel,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: WhisperModel = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        transcribe_params: Dict[str, Any] = await self._resolve_transcribe_params(context)

        if params["language"] is not None:
            transcribe_params["language"] = params["language"]
        if params["task"] is not None:
            transcribe_params["task"] = params["task"]

        params["transcribe"] = transcribe_params

        return params

    async def _resolve_transcribe_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        logprob_threshold           = await context.render_variable(self.config.params.logprob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)
        return_timestamps           = await context.render_variable(self.config.params.return_timestamps)

        params: Dict[str, Any] = {
            "beam_size": num_beams,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if compression_ratio_threshold is not None:
            params["compression_ratio_threshold"] = compression_ratio_threshold
        if logprob_threshold is not None:
            params["log_prob_threshold"] = logprob_threshold
        if no_speech_threshold is not None:
            params["no_speech_threshold"] = no_speech_threshold
        if return_timestamps:
            params["word_timestamps"] = True

        return params

    async def _transcribe(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        waveforms = [ await self._preprocess_audio(audio) for audio in audios ]

        if streaming:
            return [ self._transcribe_stream(waveform, params["transcribe"]) for waveform in waveforms ]

        return [ self._transcribe_full(waveform, params["transcribe"]) for waveform in waveforms ]

    def _transcribe_full(self, waveform: np.ndarray, params: Dict[str, Any]) -> str:
        segments, _ = self.model.transcribe(waveform, **params)
        return "".join(segment.text for segment in segments)

    def _transcribe_stream(self, waveform: np.ndarray, params: Dict[str, Any]) -> Iterator[str]:
        segments, _ = self.model.transcribe(waveform, **params)
        for segment in segments:
            yield segment.text

    async def _preprocess_audio(self, audio: MediaSource) -> np.ndarray:
        import numpy as np
        import torch
        import torchaudio.functional as F

        waveform, sample_rate = await load_audio_array(audio)

        if waveform.ndim > 1:
            waveform = waveform.mean(axis=0)  # mono

        if sample_rate != 16000:
            tensor = torch.from_numpy(waveform).float()
            waveform = F.resample(tensor, sample_rate, 16000).numpy()

        return waveform.astype(np.float32)

class FasterWhisperSpeechToTextTaskService(SpeechToTextTaskService):
    def __init__(self, id: str, config: FasterWhisperSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.config: FasterWhisperSpeechToTextModelComponentConfig = config  # For type only
        self.model: Optional[WhisperModel] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "faster-whisper", "torch", "torchaudio", "numpy" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[WhisperModel, torch.device]:
        from faster_whisper import WhisperModel

        device = self._resolve_device()
        model_path = self._get_model_path()
        model = WhisperModel(model_path, device=str(device.type), compute_type=self.config.compute_type)

        return model, device

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        return await FasterWhisperSpeechToTextTaskAction(action, self.model, self.device).run(context, loop)
