from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Protocol, Any
from mindor.dsl.schema.component import ImageToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, ImageToTextModelActionConfig
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceMultimodalModelTaskService, ComponentActionContext
from PIL import Image as PILImage
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin, GenerationMixin
    from torch import Tensor
    import torch

class WithTokenizer(Protocol):
    tokenizer: PreTrainedTokenizer

class HuggingfaceImageToTextTaskAction:
    def __init__(self, config: ImageToTextModelActionConfig, model: PreTrainedModel, processor: ProcessorMixin, device: torch.device):
        self.config: ImageToTextModelActionConfig = config
        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.processor: Union[ProcessorMixin, WithTokenizer] = processor
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        from transformers import TextIteratorStreamer, StopStringCriteria, GenerationConfig
        import torch

        image, text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(image, list))
        images: List[PILImage.Image] = [ image ] if is_single_input else image
        texts: Optional[List[str]] = [ text ] if is_single_input else text
        results = []

        batch_size        = await context.render_variable(self.config.batch_size)
        stream            = await context.render_variable(self.config.stream)
        stop_sequences    = await context.render_variable(self.config.stop_sequences)
        processor_params  = await self._resolve_processor_params(context)
        generation_params = await self._resolve_generation_params(context)

        if stream and (batch_size != 1 or len(images) != 1):
            raise ValueError("Streaming mode only supports a single input image with batch size of 1.")

        streamer = TextIteratorStreamer(self.processor.tokenizer, skip_prompt=True, skip_special_tokens=True) if stream else None
        stopping_criteria = [ StopStringCriteria(self.processor.tokenizer, stop_sequences) ] if stop_sequences else None

        for index in range(0, len(images), batch_size):
            batch_images = images[index:index + batch_size]
            batch_texts = texts[index:index + batch_size] if texts else None

            inputs: Tensor = self.processor(images=batch_images, texts=batch_texts, **processor_params)
            inputs = inputs.to(self.device)

            def _generate():
                with torch.inference_mode():
                    outputs = self.model.generate(
                        **inputs, 
                        generation_config=GenerationConfig(**generation_params),
                        stopping_criteria=stopping_criteria,
                        streamer=streamer
                    )

                outputs = self.processor.tokenizer.batch_decode(outputs, skip_special_tokens=True)
                results.extend(outputs)

            if stream:
                thread = Thread(target=_generate)
                thread.start()
            else:
                _generate()

        if stream:
            async def _stream_output_generator():
                async for chunk in AsyncStreamer(streamer, loop):
                    if chunk:
                        context.register_source("result[]", chunk)
                        yield (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else chunk

            return _stream_output_generator()
        else:
            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Union[PILImage.Image, List[PILImage.Image]], Optional[Union[str, List[str]]]]:
        image = await context.render_image(self.config.image)
        text  = await context.render_variable(self.config.text)
        
        return image, text

    async def _resolve_processor_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length)

        params = {
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
            "max_new_tokens": max_output_length,
            "min_length": min_output_length,
            "num_return_sequences": num_return_sequences,
            "do_sample": do_sample,
            "num_beams": num_beams,
            "pad_token_id": getattr(self.processor.tokenizer, "pad_token_id", None),
            "eos_token_id": getattr(self.processor.tokenizer, "eos_token_id", None),
        }

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

@register_model_task_service(ModelTaskType.IMAGE_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceImageToTextTaskService(HuggingfaceMultimodalModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await HuggingfaceImageToTextTaskAction(action, self.model, self.processor, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == ImageToTextModelArchitecture.BLIP:
            from transformers import BlipForConditionalGeneration
            return BlipForConditionalGeneration

        if self.config.architecture == ImageToTextModelArchitecture.BLIP2:
            from transformers import Blip2ForConditionalGeneration
            return Blip2ForConditionalGeneration

        if self.config.architecture == ImageToTextModelArchitecture.GIT:
            from transformers import GitForCausalLM
            return GitForCausalLM

        if self.config.architecture == ImageToTextModelArchitecture.PIX2STRUCT:
            from transformers import Pix2StructForConditionalGeneration
            return Pix2StructForConditionalGeneration

        if self.config.architecture == ImageToTextModelArchitecture.DONUT:
            from transformers import VisionEncoderDecoderModel # Donut uses this
            return VisionEncoderDecoderModel

        if self.config.architecture == ImageToTextModelArchitecture.KOSMOS2:
            from transformers import Kosmos2ForConditionalGeneration
            return Kosmos2ForConditionalGeneration
        
        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == ImageToTextModelArchitecture.BLIP:
            from transformers import BlipProcessor
            return BlipProcessor

        if self.config.architecture == ImageToTextModelArchitecture.BLIP2:
            from transformers import Blip2Processor
            return Blip2Processor

        if self.config.architecture == ImageToTextModelArchitecture.GIT:
            from transformers import GitProcessor
            return GitProcessor

        if self.config.architecture == ImageToTextModelArchitecture.PIX2STRUCT:
            from transformers import Pix2StructProcessor
            return Pix2StructProcessor

        if self.config.architecture == ImageToTextModelArchitecture.DONUT:
            from transformers import DonutProcessor
            return DonutProcessor

        if self.config.architecture == ImageToTextModelArchitecture.KOSMOS2:
            from transformers import Kosmos2Processor
            return Kosmos2Processor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")
