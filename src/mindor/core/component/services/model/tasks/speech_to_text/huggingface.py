from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import SpeechToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, SpeechToTextModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceMultimodalModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import torch

class HuggingfaceSpeechToTextTaskAction:
    def __init__(
        self,
        config: SpeechToTextModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device
    ):
        self.config: SpeechToTextModelActionConfig = config
        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        import torch
        import numpy as np

        audio_input = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(audio_input, list))
        audios: List[np.ndarray] = [audio_input] if is_single_input else audio_input
        results = []

        batch_size    = await context.render_variable(self.config.batch_size)
        language      = await context.render_variable(self.config.language)
        task          = await context.render_variable(self.config.task)
        chunk_length  = await context.render_variable(self.config.chunk_length)

        generation_params = await self._resolve_generation_params(context)

        if language is not None:
            generation_params["language"] = language
        if task is not None:
            generation_params["task"] = task

        for index in range(0, len(audios), batch_size):
            batch_audios = audios[index:index + batch_size]

            input_features = self.processor(
                batch_audios,
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

            transcriptions = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
            results.extend(transcriptions)

        result = results[0] if is_single_input else results
        return await self._render_output(context, result)

    async def _prepare_input(self, context: ComponentActionContext) -> Union[Any, List[Any]]:
        audio = await context.render_variable(self.config.audio)

        if isinstance(audio, list):
            return [await self._load_audio(a) for a in audio]
        return await self._load_audio(audio)

    async def _load_audio(self, audio_path: str) -> Any:
        import librosa
        audio_array, _ = librosa.load(audio_path, sr=16000)
        return audio_array

    async def _render_output(self, context: ComponentActionContext, result: Union[str, List[str]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_output_length           = await context.render_variable(self.config.params.max_output_length)
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        logprob_threshold           = await context.render_variable(self.config.params.logprob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)
        return_timestamps           = await context.render_variable(self.config.params.return_timestamps)

        params: Dict[str, Any] = {
            "max_new_tokens": max_output_length,
            "num_beams": num_beams,
        }

        if temperature and temperature > 0:
            params["temperature"] = temperature
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
        if self.config.architecture in (
            SpeechToTextModelArchitecture.WHISPER,
            SpeechToTextModelArchitecture.WHISPER_LARGE
        ):
            from transformers import WhisperProcessor
            return WhisperProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "transformers>=4.21.0",
            "torch",
            "librosa",
            "soundfile",
            "accelerate"
        ]
