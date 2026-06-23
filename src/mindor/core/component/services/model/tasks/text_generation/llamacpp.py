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

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        generation_params: Dict[str, Any] = {
            "max_tokens": params["max_output_length"],
        }

        if params["do_sample"]:
            if params["temperature"] is not None:
                generation_params["temperature"] = params["temperature"]
            if params["top_k"] is not None:
                generation_params["top_k"] = params["top_k"]
            if params["top_p"] is not None:
                generation_params["top_p"] = params["top_p"]
        else:
            generation_params["temperature"] = 0.0

        if params["stop_sequences"]:
            generation_params["stop"] = params["stop_sequences"] if isinstance(params["stop_sequences"], list) else [params["stop_sequences"]]

        params["generation"] = generation_params

        return params

    async def _generate(self, texts: List[str], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Iterator[str]]]:
        generation_params = params["generation"]

        if streaming:
            def _make_chunk_iter(prompt: str) -> Iterator[str]:
                for chunk in self.model(prompt, stream=True, **generation_params):
                    token = chunk["choices"][0].get("text", "")
                    if token:
                        yield token

            return [ _make_chunk_iter(text) for text in texts ]

        return [ self.model(text, stream=False, **generation_params)["choices"][0]["text"] for text in texts ]

@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.LLAMACPP)
class LlamaCppTextGenerationTaskService(LlamaCppModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await LlamaCppTextGenerationTaskAction(action, self.model).run(context, loop)
