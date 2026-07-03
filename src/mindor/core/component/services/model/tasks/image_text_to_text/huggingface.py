from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Protocol, Any, Iterator
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import HuggingfaceImageTextToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, ImageTextToTextModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from ...base.huggingface.streamer import BatchTextIteratorStreamer
from .common import ImageTextToTextTaskAction
from PIL import Image as PILImage
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin, GenerationMixin
    from torch import Tensor
    import torch

class WithTokenizer(Protocol):
    tokenizer: PreTrainedTokenizer

class HuggingfaceImageTextToTextTaskAction(ImageTextToTextTaskAction):
    def __init__(
        self,
        config: ImageTextToTextModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
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
            "truncation": False,
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

    def _build_messages(self, prompt_text: str, system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []

        if system_prompt:
            messages.append({ "role": "system", "content": [{ "type": "text", "text": system_prompt }] })

        messages.append({
            "role": "user",
            "content": [
                { "type": "image" },
                { "type": "text", "text": prompt_text },
            ],
        })

        return messages

    async def _generate(
        self,
        images: List[PILImage.Image],
        prompts: List[str],
        system_prompt: Optional[str],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        from transformers import StopStringCriteria, GenerationConfig
        import torch

        stopping_criteria = [ StopStringCriteria(self.processor.tokenizer, params["stop_sequences"]) ] if params["stop_sequences"] else None

        chat_prompts: List[str] = [
            self.processor.apply_chat_template(
                self._build_messages(prompt, system_prompt),
                tokenize=False,
                add_generation_prompt=True,
            )
            for prompt in prompts
        ]

        inputs: Tensor = self.processor(images=images, text=chat_prompts, **params["processor"])
        inputs = inputs.to(self.device)

        input_lengths = inputs["input_ids"].shape[1] if "input_ids" in inputs else None

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

        if input_lengths is not None:
            outputs = outputs[:, input_lengths:]

        return self.processor.tokenizer.batch_decode(outputs, skip_special_tokens=True)

@register_model_task_service(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceImageTextToTextTaskService(HuggingfaceMultimodalModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        return await HuggingfaceImageTextToTextTaskAction(action, self.model, self.processor, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.AUTO:
            from transformers import AutoModelForVision2Seq
            return AutoModelForVision2Seq

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.QWEN2_VL:
            from transformers import Qwen2VLForConditionalGeneration
            return Qwen2VLForConditionalGeneration

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.QWEN2_5_VL:
            from transformers import Qwen2_5_VLForConditionalGeneration
            return Qwen2_5_VLForConditionalGeneration

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.LLAVA:
            from transformers import LlavaForConditionalGeneration
            return LlavaForConditionalGeneration

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.LLAVA_NEXT:
            from transformers import LlavaNextForConditionalGeneration
            return LlavaNextForConditionalGeneration

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.IDEFICS3:
            from transformers import Idefics3ForConditionalGeneration
            return Idefics3ForConditionalGeneration

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.INTERNVL:
            from transformers import InternVLForConditionalGeneration
            return InternVLForConditionalGeneration

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.AUTO:
            from transformers import AutoProcessor
            return AutoProcessor

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.QWEN2_VL:
            from transformers import Qwen2VLProcessor
            return Qwen2VLProcessor

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.QWEN2_5_VL:
            from transformers import Qwen2_5_VLProcessor
            return Qwen2_5_VLProcessor

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.LLAVA:
            from transformers import LlavaProcessor
            return LlavaProcessor

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.LLAVA_NEXT:
            from transformers import LlavaNextProcessor
            return LlavaNextProcessor

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.IDEFICS3:
            from transformers import Idefics3Processor
            return Idefics3Processor

        if self.config.architecture == HuggingfaceImageTextToTextModelArchitecture.INTERNVL:
            from transformers import InternVLProcessor
            return InternVLProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")
