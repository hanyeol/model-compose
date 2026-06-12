from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import SpeechToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, SpeechToTextModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceMultimodalModelTaskService, ComponentActionContext
from .common import SpeechToTextTaskAction
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import torch

class HuggingfaceSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: SpeechToTextModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor

    async def _transcribe(self, audios: List[Tuple[Any, int]], context: ComponentActionContext) -> List[str]:
        import torch

        language      = await context.render_variable(self.config.language)
        task          = await context.render_variable(self.config.task)
        chunk_length  = await context.render_variable(self.config.chunk_length)

        generation_params = await self._resolve_generation_params(context)

        if language is not None:
            generation_params["language"] = language
        if task is not None:
            generation_params["task"] = task

        waveforms = [ self._preprocess_audio(waveform, sample_rate) for waveform, sample_rate in audios ]

        input_features = self.processor(
            waveforms,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True,
            chunk_length=chunk_length
        )
        input_features = input_features.to(self.device)

        with torch.inference_mode():
            predicted_ids = self.model.generate(
                **input_features,
                **generation_params
            )

        return self.processor.batch_decode(predicted_ids, skip_special_tokens=True)

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_output_length           = await context.render_variable(self.config.params.max_output_length)
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        logprob_threshold           = await context.render_variable(self.config.params.logprob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)
        return_timestamps           = await context.render_variable(self.config.params.return_timestamps)

        params: Dict[str, Any] = {
            "num_beams": num_beams,
        }

        if max_output_length is not None:
            params["max_new_tokens"] = max_output_length

        if temperature is not None:
            params["temperature"] = temperature
            if temperature > 0:
                params["do_sample"] = True

        if compression_ratio_threshold is not None:
            params["compression_ratio_threshold"] = compression_ratio_threshold
        if logprob_threshold is not None:
            params["logprob_threshold"] = logprob_threshold
        if no_speech_threshold is not None:
            params["no_speech_threshold"] = no_speech_threshold
        if return_timestamps:
            params["return_timestamps"] = return_timestamps

        return params

    def _preprocess_audio(self, waveform: Any, sample_rate: int) -> Any:
        import numpy as np
        import torch
        import torchaudio.functional as F

        if waveform.ndim > 1:
            waveform = waveform.mean(axis=0)  # mono

        if sample_rate != 16000:
            tensor = torch.from_numpy(waveform).float()
            waveform = F.resample(tensor, sample_rate, 16000).numpy()

        return waveform.astype(np.float32)

@register_model_task_service(ModelTaskType.SPEECH_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceSpeechToTextTaskService(HuggingfaceMultimodalModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceSpeechToTextTaskAction(action, self.model, self.processor, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture in (
            SpeechToTextModelArchitecture.WHISPER,
            SpeechToTextModelArchitecture.WHISPER_LARGE
        ):
            from transformers import WhisperForConditionalGeneration
            return WhisperForConditionalGeneration

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture in [ SpeechToTextModelArchitecture.WHISPER, SpeechToTextModelArchitecture.WHISPER_LARGE ]:
            from transformers import WhisperProcessor
            return WhisperProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "transformers>=4.21.0",
            "torch",
            "torchaudio",
            "accelerate"
        ]
