from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
from .common import TextGenerationTaskAction
import asyncio

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppTextGenerationTaskAction(TextGenerationTaskAction):
    def __init__(
        self,
        config: TextGenerationModelActionConfig,
        model: Llama,
    ):
        super().__init__(config)

        self.model: Llama = model

    async def _generate(self, texts: List[str], context: ComponentActionContext, streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Iterator[str]]]:
        generation_params = await self._resolve_generation_params(context)

        if streaming:
            def _make_chunk_iter(prompt: str) -> Iterator[str]:
                for chunk in self.model(prompt, stream=True, **generation_params):
                    token = chunk["choices"][0].get("text", "")
                    if token:
                        yield token

            return [ _make_chunk_iter(text) for text in texts ]

        return [ self.model(text, stream=False, **generation_params)["choices"][0]["text"] for text in texts ]

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_output_length = await context.render_variable(self.config.params.max_output_length)
        do_sample         = await context.render_variable(self.config.params.do_sample)
        temperature       = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k             = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p             = await context.render_variable(self.config.params.top_p) if do_sample else None
        stop_sequences    = await context.render_variable(self.config.stop_sequences)

        params: Dict[str, Any] = {
            "max_tokens": max_output_length,
        }

        if do_sample:
            if temperature is not None:
                params["temperature"] = temperature
            if top_k is not None:
                params["top_k"] = top_k
            if top_p is not None:
                params["top_p"] = top_p
        else:
            params["temperature"] = 0.0

        if stop_sequences:
            params["stop"] = stop_sequences if isinstance(stop_sequences, list) else [stop_sequences]

        return params


@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.LLAMACPP)
class LlamaCppTextGenerationTaskService(LlamaCppModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await LlamaCppTextGenerationTaskAction(action, self.model).run(context, loop)
