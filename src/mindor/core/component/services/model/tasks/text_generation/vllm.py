from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from .common import TextGenerationTaskAction
import asyncio, ulid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine, SamplingParams

class VllmTextGenerationTaskAction(TextGenerationTaskAction):
    def __init__(
        self,
        config: TextGenerationModelActionConfig,
        engine: AsyncLLMEngine,
    ):
        super().__init__(config)

        self.engine: AsyncLLMEngine = engine

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        from vllm import SamplingParams

        params = await super()._resolve_params(context)

        num_return_sequences = await context.render_variable(self.config.params.num_return_sequences)

        sampling_params: Dict[str, Any] = { "n": num_return_sequences }
        if params["max_output_length"] is not None:
            sampling_params["max_tokens"] = params["max_output_length"]

        if params["do_sample"]:
            if params["temperature"] is not None:
                sampling_params["temperature"] = params["temperature"]
            if params["top_k"] is not None:
                sampling_params["top_k"] = params["top_k"]
            if params["top_p"] is not None:
                sampling_params["top_p"] = params["top_p"]
        else:
            sampling_params["temperature"] = 0.0

        if params["stop_sequences"]:
            sampling_params["stop"] = params["stop_sequences"] if isinstance(params["stop_sequences"], list) else [params["stop_sequences"]]

        params["sampling"] = SamplingParams(**sampling_params)

        return params

    async def _generate(self, texts: List[str], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        sampling = params["sampling"]

        if streaming:
            return [ self._stream_one(prompt, sampling) for prompt in texts ]

        return [ await self._generate_one(prompt, sampling) for prompt in texts ]

    async def _generate_one(self, prompt: str, sampling: SamplingParams) -> str:
        request_id = f"request-{ulid.ulid()}"
        text = ""
        async for output in self.engine.generate(prompt, sampling, request_id=request_id):
            if output.outputs:
                text = output.outputs[0].text
        return text

    async def _stream_one(self, prompt: str, sampling: SamplingParams) -> AsyncIterator[str]:
        request_id = f"request-{ulid.ulid()}"
        previous = ""
        async for output in self.engine.generate(prompt, sampling, request_id=request_id):
            text = output.outputs[0].text if output.outputs else ""
            delta = text[len(previous):]
            previous = text
            if delta:
                yield delta

@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.VLLM)
class VllmTextGenerationTaskService(VllmModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await VllmTextGenerationTaskAction(action, self.engine).run(context, loop)
