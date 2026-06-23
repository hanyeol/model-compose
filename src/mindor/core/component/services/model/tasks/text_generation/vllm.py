from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from .common import TextGenerationTaskAction
import asyncio, uuid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine

class VllmTextGenerationTaskAction(TextGenerationTaskAction):
    def __init__(
        self,
        config: TextGenerationModelActionConfig,
        engine: AsyncLLMEngine,
    ):
        super().__init__(config)

        self.engine: AsyncLLMEngine = engine

    async def _generate(self, texts: List[str], context: ComponentActionContext, streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        num_return_sequences = await context.render_variable(self.config.params.num_return_sequences)
        sampling = await self._build_sampling_params(context, n=num_return_sequences)

        if streaming:
            request_id = f"gen-{uuid.uuid4().hex}"

            async def _chunk_generator():
                previous = ""
                async for output in self.engine.generate(texts[0], sampling, request_id=request_id):
                    text = output.outputs[0].text if output.outputs else ""
                    delta = text[len(previous):]
                    previous = text
                    if delta:
                        yield { "choices": [ { "text": delta } ] }

            return _chunk_generator()

        choices: List[List[Dict[str, Any]]] = []
        for prompt in texts:
            request_id = f"gen-{uuid.uuid4().hex}"
            final_outputs: List[Any] = []
            async for output in self.engine.generate(prompt, sampling, request_id=request_id):
                final_outputs = output.outputs or []
            choices.append([ { "text": o.text } for o in final_outputs ])

        return { "choices": choices }

    async def _build_sampling_params(self, context: ComponentActionContext, n: int = 1) -> Any:
        from vllm import SamplingParams

        max_output_length = await context.render_variable(self.config.params.max_output_length)
        do_sample         = await context.render_variable(self.config.params.do_sample)
        temperature       = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k             = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p             = await context.render_variable(self.config.params.top_p) if do_sample else None
        stop_sequences    = await context.render_variable(self.config.stop_sequences)

        params: Dict[str, Any] = { "n": n }
        if max_output_length is not None:
            params["max_tokens"] = max_output_length

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

        return SamplingParams(**params)


@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.VLLM)
class VllmTextGenerationTaskService(VllmModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await VllmTextGenerationTaskAction(action, self.engine).run(context, loop)
