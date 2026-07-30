from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Iterator, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.streamer import SyncGeneratorStreamer
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

    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        loop = asyncio.get_running_loop()

        if streaming:
            # llama_cpp yields tokens synchronously; wrap each per-prompt generator
            # with SyncGeneratorStreamer so the caller can consume it via async for.
            return [
                SyncGeneratorStreamer(self._stream_text(prompt, params["generation"], cancellation_token), loop)
                for prompt in texts
            ]

        def _generate() -> List[str]:
            return [ self._generate_text(prompt, params["generation"], cancellation_token) for prompt in texts ]

        return await self._run_in_executor(_generate)

    def _generate_text(
        self,
        prompt: str,
        generation_params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        if cancellation_token is not None:
            chunks: List[str] = []
            for token in self._stream_text(prompt, generation_params, cancellation_token):
                chunks.append(token)
            return "".join(chunks)

        return self.model(prompt, stream=False, **generation_params)["choices"][0]["text"]

    def _stream_text(
        self,
        prompt: str,
        generation_params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Iterator[str]:
        for chunk in self.model(prompt, stream=True, **generation_params):
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break
            token = chunk["choices"][0].get("text", "")
            if token:
                yield token

@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.LLAMACPP)
class LlamaCppTextGenerationTaskService(LlamaCppModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LlamaCppTextGenerationTaskAction(action, self.model).run(context)
