from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import HuggingfaceSpeechToTextModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from ....base import ComponentActionContext
from ....base.huggingface.multimodal import HuggingfaceMultimodalModelTaskDriver
from ....base.huggingface.cancellation import create_cancellation_criteria
from ..common import SpeechToTextTaskAction

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin, StoppingCriteriaList
    import numpy as np
    import torch

class HuggingfaceSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: HuggingfaceSpeechToTextModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        log_prob_threshold          = await context.render_variable(self.config.params.log_prob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)

        params: Dict[str, Any] = {
            "num_beams": num_beams,
        }

        if temperature is not None:
            params["temperature"] = temperature
            if temperature > 0:
                params["do_sample"] = True

        if compression_ratio_threshold is not None:
            params["compression_ratio_threshold"] = compression_ratio_threshold

        if log_prob_threshold is not None:
            params["logprob_threshold"] = log_prob_threshold

        if no_speech_threshold is not None:
            params["no_speech_threshold"] = no_speech_threshold

        return params

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            audio = await AudioBufferStreamer(audio, sample_rate=16000, channel="mono").collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _build_stopping_criteria(self, cancellation_token: Optional[CancellationToken]) -> Optional[StoppingCriteriaList]:
        from transformers import StoppingCriteriaList

        criteria = []

        if cancellation_token:
            criteria.append(create_cancellation_criteria(cancellation_token))

        return StoppingCriteriaList(criteria) if criteria else None

class HuggingfaceSpeechToTextBaseDriver(HuggingfaceMultimodalModelTaskDriver):
    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchaudio", "torchcodec"),
            "transformers>=4.52.0",
            "accelerate",
            "soxr",
        ]
