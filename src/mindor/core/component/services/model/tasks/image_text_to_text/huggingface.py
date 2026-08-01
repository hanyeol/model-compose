from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Protocol, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import HuggingfaceImageTextToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, ImageTextToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.streamer import SyncGeneratorStreamer
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

        processor_params: Dict[str, Any] = await self._resolve_processor_params()

        if params["max_input_length"] is not None:
            processor_params["max_length"] = params["max_input_length"]
            processor_params["truncation"] = True

        generation_params: Dict[str, Any] = await self._resolve_generation_params(context)

        generation_params["num_return_sequences"] = params["num_return_sequences"]
        generation_params["do_sample"] = params["do_sample"]

        if params["max_output_length"] is not None:
            generation_params["max_new_tokens"] = params["max_output_length"]

        if params["do_sample"]:
            if params["temperature"] is not None:
                generation_params["temperature"] = params["temperature"]
            if params["top_k"] is not None:
                generation_params["top_k"] = params["top_k"]
            if params["top_p"] is not None:
                generation_params["top_p"] = params["top_p"]

        params["processor"]  = processor_params
        params["generation"] = generation_params

        return params

    async def _resolve_processor_params(self) -> Dict[str, Any]:
        return {
            "return_tensors": "pt",
            "padding": True,
            "truncation": False,
        }

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        min_output_length = await context.render_variable(self.config.min_output_length)
        num_beams         = await context.render_variable(self.config.params.num_beams)
        length_penalty    = await context.render_variable(self.config.params.length_penalty) if num_beams > 1 else None
        early_stopping    = await context.render_variable(self.config.params.early_stopping) if num_beams > 1 else False

        params: Dict[str, Any] = {
            "min_length": min_output_length,
            "num_beams": num_beams,
            "pad_token_id": getattr(self.processor.tokenizer, "pad_token_id", None),
            "eos_token_id": getattr(self.processor.tokenizer, "eos_token_id", None),
        }

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

    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        prompts: List[str],
        system_prompt: Optional[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        loop = asyncio.get_running_loop()

        def _generate() -> Union[List[str], List[Any]]:
            from transformers import StopStringCriteria, GenerationConfig
            import torch

            stopping_criteria = [ StopStringCriteria(self.processor.tokenizer, params["stop_sequences"]) ] if params["stop_sequences"] else None

            rendered_prompts = [
                self.processor.apply_chat_template(
                    self._build_messages(prompt, system_prompt),
                    tokenize=False,
                    add_generation_prompt=True,
                )
                for prompt in prompts
            ]

            inputs: Tensor = self.processor(images=images, text=rendered_prompts, **params["processor"])
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

        results = await self._run_in_executor(_generate)

        if streaming:
            return [ SyncGeneratorStreamer(streamer, loop) for streamer in results ]

        return results

@register_model_task_service(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceImageTextToTextTaskService(HuggingfaceMultimodalModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceImageTextToTextTaskAction(action, self.model, self.processor, self.device).run(context)

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
