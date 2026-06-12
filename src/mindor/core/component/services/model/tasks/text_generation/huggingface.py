from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from mindor.dsl.schema.component import TextGenerationModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceLanguageModelTaskService, ComponentActionContext
from .common import TextGenerationTaskAction
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, GenerationMixin
    from torch import Tensor
    import torch

class HuggingfaceTextGenerationTaskAction(TextGenerationTaskAction):
    def __init__(
        self,
        config: TextGenerationModelActionConfig,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def _generate(self, texts: List[str], context: ComponentActionContext, streaming: bool) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        from transformers import StopStringCriteria, GenerationConfig
        import torch

        stop_sequences    = await context.render_variable(self.config.stop_sequences)
        tokenizer_params  = await self._resolve_tokenizer_params(context)
        generation_params = await self._resolve_generation_params(context)

        stopping_criteria = [ StopStringCriteria(self.tokenizer, stop_sequences) ] if stop_sequences else None

        inputs: Dict[str, Tensor] = self.tokenizer(texts, **tokenizer_params)
        inputs = { k: v.to(self.device) for k, v in inputs.items() }

        if streaming:
            from transformers import TextIteratorStreamer

            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True)

            def _run():
                with torch.inference_mode():
                    self.model.generate(
                        **inputs,
                        generation_config=GenerationConfig(**generation_params),
                        stopping_criteria=stopping_criteria,
                        streamer=streamer
                    )

            Thread(target=_run, daemon=True).start()

            def _chunk_iterator():
                for token in streamer:
                    if token:
                        yield {"choices": [{"text": token}]}

            return _chunk_iterator()
        else:
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    generation_config=GenerationConfig(**generation_params),
                    stopping_criteria=stopping_criteria,
                )

            decoded = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
            return {"choices": [{"text": text} for text in decoded]}

    async def _resolve_tokenizer_params(self, context: ComponentActionContext) -> Dict[str, Any]:
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

        params: Dict[str, Any] = {
            "min_length": min_output_length,
            "num_return_sequences": num_return_sequences,
            "do_sample": do_sample,
            "num_beams": num_beams,
        }

        if max_output_length is not None:
            params["max_new_tokens"] = max_output_length

        for token in [ "pad_token_id", "eos_token_id", "bos_token_id" ]:
            token_id = getattr(self.tokenizer, token, None)
            if token_id is not None:
                params[token] = token_id

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
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
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
