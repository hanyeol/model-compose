from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import TextGenerationModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceLanguageModelTaskService, ComponentActionContext
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, GenerationMixin
    from torch import Tensor
    import torch

class HuggingfaceTextGenerationTaskAction:
    def __init__(self, config: TextGenerationModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer, device: torch.device):
        self.config: TextGenerationModelActionConfig = config
        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        from transformers import TextIteratorStreamer, StopStringCriteria, GenerationConfig
        import torch

        text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(text, list))
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        batch_size        = await context.render_variable(self.config.batch_size)
        stop_sequences    = await context.render_variable(self.config.stop_sequences)
        stream            = await context.render_variable(self.config.stream)
        tokenizer_params  = await self._resolve_tokenizer_params(context)
        generation_params = await self._resolve_generation_params(context)

        if stream and (batch_size != 1 or len(texts) != 1):
            raise ValueError("Streaming mode only supports a single input text with batch size of 1.")

        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True) if stream else None
        stopping_criteria = [ StopStringCriteria(self.tokenizer, stop_sequences) ] if stop_sequences else None

        for index in range(0, len(texts), batch_size):
            batch_texts = texts[index:index + batch_size]
            inputs: Dict[str, Tensor] = self.tokenizer(batch_texts, **tokenizer_params)
            inputs = { k: v.to(self.device) for k, v in inputs.items() }

            def _generate():
                with torch.inference_mode():
                    outputs = self.model.generate(
                        **inputs, 
                        generation_config=GenerationConfig(**generation_params),
                        stopping_criteria=stopping_criteria,
                        streamer=streamer
                    )

                if not stream:
                    outputs = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
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

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    async def _resolve_tokenizer_params(self, context: ComponentActionContext) -> Dict[str, Any]:
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
            "pad_token_id": getattr(self.tokenizer, "pad_token_id", None),
            "eos_token_id": getattr(self.tokenizer, "eos_token_id", None),
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

@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.HUGGINGFACE)
class HuggingfaceTextGenerationTaskService(HuggingfaceLanguageModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await HuggingfaceTextGenerationTaskAction(action, self.model, self.tokenizer, self.device).run(context, loop)
    
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == TextGenerationModelArchitecture.CAUSAL:
            from transformers import AutoModelForCausalLM
            return AutoModelForCausalLM

        if self.config.architecture == TextGenerationModelArchitecture.SEQ2SEQ:
            from transformers import AutoModelForSeq2SeqLM
            return AutoModelForSeq2SeqLM

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
