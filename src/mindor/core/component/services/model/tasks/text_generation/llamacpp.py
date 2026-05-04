from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppTextGenerationTaskAction:
    def __init__(
        self,
        config: TextGenerationModelActionConfig,
        model: Llama,
    ):
        self.config: TextGenerationModelActionConfig = config
        self.model: Llama = model

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text = await self._prepare_input(context)
        is_single_input: bool = not isinstance(text, list)
        texts: List[str] = [text] if is_single_input else text

        streaming         = await context.render_variable(self.config.streaming)
        generation_params = await self._resolve_generation_params(context)

        if streaming and len(texts) != 1:
            raise ValueError("Streaming mode only supports a single input text")

        if streaming:
            response = self.model(texts[0], stream=True, **generation_params)

            async def _stream_output_generator():
                for chunk in response:
                    token = chunk["choices"][0].get("text", "")
                    if token:
                        yield await self._render_output_chunk(context, token)

            return _stream_output_generator()
        else:
            results = []
            for text_input in texts:
                response = self.model(text_input, stream=False, **generation_params)
                results.append(response["choices"][0]["text"])

            result = results[0] if is_single_input else results
            return await self._render_output(context, result)

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    async def _render_output_chunk(self, context: ComponentActionContext, chunk: str) -> Any:
        context.register_source("result[]", chunk)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else chunk

    async def _render_output(self, context: ComponentActionContext, result: Union[str, List[str]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

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
