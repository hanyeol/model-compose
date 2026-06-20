from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Iterator, Any
from mindor.dsl.schema.component import HuggingfaceSpeechToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, SpeechToTextModelActionConfig
from mindor.core.utils.streaming.audio import load_audio_array
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from ...base.huggingface.streamer import BatchTextIteratorStreamer
from .common import SpeechToTextTaskAction
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import numpy as np
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

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        generation_params: Dict[str, Any] = await self._resolve_generation_params(context)

        if params["language"] is not None:
            generation_params["language"] = params["language"]
        if params["task"] is not None:
            generation_params["task"] = params["task"]

        params["generation"] = generation_params

        return params

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

    async def _transcribe(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Iterator[str]]]:
        import torch

        waveforms = [ await self._preprocess_audio(audio) for audio in audios ]

        input_features = self.processor(
            waveforms,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True,
            chunk_length=params["chunk_length"]
        )
        input_features = input_features.to(self.device)

        if streaming:
            streamer = BatchTextIteratorStreamer(
                self.processor.tokenizer,
                batch_size=len(waveforms),
                skip_prompt=True,
                skip_special_tokens=True
            )

            def _run():
                with torch.inference_mode():
                    self.model.generate(
                        **input_features,
                        **params["generation"],
                        streamer=streamer
                    )

            Thread(target=_run, daemon=True).start()

            return [ streamer[index] for index in range(len(waveforms)) ]

        with torch.inference_mode():
            predicted_ids = self.model.generate(
                **input_features,
                **params["generation"]
            )

        return self.processor.batch_decode(predicted_ids, skip_special_tokens=True)

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
        if self.config.architecture == HuggingfaceSpeechToTextModelArchitecture.WHISPER:
            from transformers import WhisperForConditionalGeneration
            return WhisperForConditionalGeneration

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceSpeechToTextModelArchitecture.WHISPER:
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
