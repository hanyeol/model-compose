from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, TextToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from ...base.huggingface.streamer import BatchTextIteratorStreamer
from .common import TextToTextTaskAction
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, GenerationMixin
    from torch import Tensor
    import torch

class HuggingfaceTextToTextTaskAction(TextToTextTaskAction):
    def __init__(
        self,
        config: TextToTextModelActionConfig,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        max_input_length     = await context.render_variable(self.config.max_input_length)
        min_output_length    = await context.render_variable(self.config.params.min_output_length)
        num_beams            = await context.render_variable(self.config.params.num_beams)
        length_penalty       = await context.render_variable(self.config.params.length_penalty) if num_beams > 1 else None
        early_stopping       = await context.render_variable(self.config.params.early_stopping) if num_beams > 1 else False

        tokenizer_params: Dict[str, Any] = {
            "return_tensors": "pt",
            "padding": True,
            "truncation": False,
        }

        if max_input_length is not None:
            tokenizer_params["max_length"] = max_input_length
            tokenizer_params["truncation"] = True

        generation_params: Dict[str, Any] = {
            "min_length": min_output_length,
            "num_return_sequences": params["num_return_sequences"],
            "do_sample": params["do_sample"],
            "num_beams": num_beams,
        }

        if params["max_output_length"] is not None:
            generation_params["max_new_tokens"] = params["max_output_length"]

        for token in [ "pad_token_id", "eos_token_id", "bos_token_id" ]:
            token_id = getattr(self.tokenizer, token, None)
            if token_id is not None:
                generation_params[token] = token_id

        if params["do_sample"]:
            if params["temperature"] is not None:
                generation_params["temperature"] = params["temperature"]
            if params["top_k"] is not None:
                generation_params["top_k"] = params["top_k"]
            if params["top_p"] is not None:
                generation_params["top_p"] = params["top_p"]

        if num_beams > 1:
            if length_penalty is not None:
                generation_params["length_penalty"] = length_penalty
            generation_params["early_stopping"] = early_stopping

        params["tokenizer"] = tokenizer_params
        params["generation"] = generation_params

        return params

    async def _generate(
        self,
        texts: List[str],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None
    ) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        from transformers import StopStringCriteria, GenerationConfig
        import torch

        stopping_criteria = [ StopStringCriteria(self.tokenizer, stop_sequences) ] if params["stop_sequences"] else None

        inputs: Dict[str, Tensor] = self.tokenizer(texts, **params["tokenizer"])
        inputs = { k: v.to(self.device) for k, v in inputs.items() }

        if streaming:
            streamer = BatchTextIteratorStreamer(
                self.tokenizer,
                batch_size=len(texts),
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

            return [ streamer[index] for index in range(len(texts)) ]

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                generation_config=GenerationConfig(**params["generation"]),
                stopping_criteria=stopping_criteria,
            )

        return self.tokenizer.batch_decode(outputs, skip_special_tokens=True)

@register_model_task_service(ModelTaskType.TEXT_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceTextToTextTaskService(HuggingfaceLanguageModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceTextToTextTaskAction(action, self.model, self.tokenizer, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForSeq2SeqLM
        return AutoModelForSeq2SeqLM

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
