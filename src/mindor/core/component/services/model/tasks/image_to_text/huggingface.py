from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Protocol, Any, Iterator
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import HuggingfaceImageToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, ImageToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from ...base.huggingface.streamer import BatchTextIteratorStreamer
from ...base.huggingface.cancellation import create_cancellation_criteria
from .common import ImageToTextTaskAction
from PIL import Image as PILImage
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin, GenerationMixin, StoppingCriteriaList
    from torch import Tensor
    import torch

class WithTokenizer(Protocol):
    tokenizer: PreTrainedTokenizer

class HuggingfaceImageToTextTaskAction(ImageToTextTaskAction):
    def __init__(
        self,
        config: ImageToTextModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device
    ):
        super().__init__(config)

        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.processor: Union[ProcessorMixin, WithTokenizer] = processor
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        stop_sequences = await context.render_variable(self.config.stop_sequences)

        processor_params  = await self._resolve_processor_params(context)
        generation_params = await self._resolve_generation_params(context)

        params.update({
            "stop_sequences": stop_sequences,
            "processor":      processor_params,
            "generation":     generation_params,
        })

        return params

    async def _resolve_processor_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length)

        params: Dict[str, Any] = {
            "return_tensors": "pt",
            "padding": True,
            "truncation": False
        }

        if max_input_length is not None:
            params["max_length"] = max_input_length
            params["truncation"] = True

        return params

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_output_length    = await context.render_variable(self.config.params.max_output_length)
        min_output_length    = await context.render_variable(self.config.params.min_output_length)
        num_return_sequences = await context.render_variable(self.config.params.num_return_sequences)
        do_sample            = await context.render_variable(self.config.params.do_sample)
        temperature          = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k                = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p                = await context.render_variable(self.config.params.top_p) if do_sample else None
        num_beams            = await context.render_variable(self.config.params.num_beams)
        length_penalty       = await context.render_variable(self.config.params.length_penalty) if num_beams > 1 else None
        early_stopping       = await context.render_variable(self.config.params.early_stopping) if num_beams > 1 else False

        params = {
            "min_length": min_output_length,
            "num_return_sequences": num_return_sequences,
            "do_sample": do_sample,
            "num_beams": num_beams,
            "pad_token_id": getattr(self.processor.tokenizer, "pad_token_id", None),
            "eos_token_id": getattr(self.processor.tokenizer, "eos_token_id", None),
        }

        if max_output_length is not None:
            params["max_new_tokens"] = max_output_length

        if do_sample:
            if temperature is not None:
                params["temperature"] = temperature
            if top_k is not None:
                params["top_k"] = top_k
            if top_p is not None:
                params["top_p"] = top_p

        if num_beams > 1:
            if length_penalty is not None:
                params["length_penalty"] = length_penalty
            params["early_stopping"] = early_stopping

        return params

    async def _generate(
        self,
        images: List[PILImage.Image],
        prompts: Optional[List[str]],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None
    ) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        from transformers import GenerationConfig
        import torch

        inputs: Tensor = self.processor(images=images, text=prompts, **params["processor"])
        inputs = inputs.to(self.device)

        stopping_criteria = self._build_stopping_criteria(params["stop_sequences"], cancellation_token)

        if streaming:
            streamer = BatchTextIteratorStreamer(
                self.processor.tokenizer,
                batch_size=len(images),
                skip_prompt=True,
                skip_special_tokens=True,
            )

            def _run():
                with torch.inference_mode():
                    self.model.generate(
                        **inputs,
                        generation_config=GenerationConfig(**params["generation"]),
                        stopping_criteria=stopping_criteria,
                        streamer=streamer,
                    )

            Thread(target=_run, daemon=True).start()

            return [ streamer[index] for index in range(len(images)) ]

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                generation_config=GenerationConfig(**params["generation"]),
                stopping_criteria=stopping_criteria,
            )

        return self.processor.tokenizer.batch_decode(outputs, skip_special_tokens=True)

    def _build_stopping_criteria(
        self,
        stop_sequences: Optional[List[str]],
        cancellation_token: Optional[CancellationToken]
    ) -> Optional[StoppingCriteriaList]:
        from transformers import StopStringCriteria, StoppingCriteriaList

        criteria = []
 
        if stop_sequences:
            criteria.append(StopStringCriteria(self.processor.tokenizer, stop_sequences))
    
        if cancellation_token:
            criteria.append(create_cancellation_criteria(cancellation_token))

        return StoppingCriteriaList(criteria) if criteria else None

@register_model_task_service(ModelTaskType.IMAGE_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceImageToTextTaskService(HuggingfaceMultimodalModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceImageToTextTaskAction(action, self.model, self.processor, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.AUTO:
            from transformers import AutoModelForVision2Seq
            return AutoModelForVision2Seq

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.BLIP:
            from transformers import BlipForConditionalGeneration
            return BlipForConditionalGeneration

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.BLIP2:
            from transformers import Blip2ForConditionalGeneration
            return Blip2ForConditionalGeneration

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.GIT:
            from transformers import GitForCausalLM
            return GitForCausalLM

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.PIX2STRUCT:
            from transformers import Pix2StructForConditionalGeneration
            return Pix2StructForConditionalGeneration

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.DONUT:
            from transformers import VisionEncoderDecoderModel # Donut uses this
            return VisionEncoderDecoderModel

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.KOSMOS2:
            from transformers import Kosmos2ForConditionalGeneration
            return Kosmos2ForConditionalGeneration

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.AUTO:
            from transformers import AutoProcessor
            return AutoProcessor

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.BLIP:
            from transformers import BlipProcessor
            return BlipProcessor

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.BLIP2:
            from transformers import Blip2Processor
            return Blip2Processor

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.GIT:
            from transformers import GitProcessor
            return GitProcessor

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.PIX2STRUCT:
            from transformers import Pix2StructProcessor
            return Pix2StructProcessor

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.DONUT:
            from transformers import DonutProcessor
            return DonutProcessor

        if self.config.architecture == HuggingfaceImageToTextModelArchitecture.KOSMOS2:
            from transformers import Kosmos2Processor
            return Kosmos2Processor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")
