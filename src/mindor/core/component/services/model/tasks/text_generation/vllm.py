from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from .common import TextGenerationTaskAction
import asyncio, ulid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine, SamplingParams

_STREAM_QUEUE_SIZE = 32

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

        if params["max_input_length"] is not None:
            logging.warning("vLLM backend does not support max_input_length; ignoring configured value %r.", params["max_input_length"])

        sampling_params: Dict[str, Any] = { "n": params["num_return_sequences"] }

        if params["max_output_length"] is not None:
            sampling_params["max_tokens"] = params["max_output_length"]

        if params["min_output_length"] and params["min_output_length"] > 1:
            sampling_params["min_tokens"] = params["min_output_length"]

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

    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[List[str]], List[List[AsyncIterator[str]]]]:
        num_return_sequences = params["num_return_sequences"] or 1

        if streaming:
            return [
                self._stream_text(prompt, params["sampling"], num_return_sequences, cancellation_token)
                for prompt in texts
            ]

        return [
            await self._generate_text(prompt, params["sampling"], num_return_sequences, cancellation_token)
            for prompt in texts
        ]

    async def _generate_text(
        self,
        prompt: str,
        sampling: SamplingParams,
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[str]:
        request_id = f"request-{ulid.ulid()}"
        texts: List[str] = [ "" ] * num_return_sequences

        async for output in self.engine.generate(prompt, sampling, request_id=request_id):
            if cancellation_token is not None and cancellation_token.is_cancelled():
                await self.engine.abort(request_id)
                break

            for sequence in output.outputs:
                texts[sequence.index] = sequence.text

        return texts

    def _stream_text(
        self,
        prompt: str,
        sampling: SamplingParams,
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AsyncIterator[str]]:
        # vLLM emits every sequence's cumulative text in one shared async
        # iterator, so fan it out into n independent per-sequence queues so
        # each returned iterator can be consumed on its own. Queues are
        # bounded to apply backpressure on the engine when consumers are
        # slow, and the fan-out task is aborted if any consumer stops early.
        request_id = f"request-{ulid.ulid()}"
        queues: List[asyncio.Queue] = [ asyncio.Queue(maxsize=_STREAM_QUEUE_SIZE) for _ in range(num_return_sequences) ]
        active = [ True ] * num_return_sequences
        end = object()

        async def _fan_out_sequences():
            previous = [ "" ] * num_return_sequences

            try:
                async for output in self.engine.generate(prompt, sampling, request_id=request_id):
                    if cancellation_token is not None and cancellation_token.is_cancelled():
                        break

                    if not any(active):
                        break

                    for sequence in output.outputs:
                        index = sequence.index

                        if not active[index]:
                            continue

                        delta = sequence.text[len(previous[index]):]
                        previous[index] = sequence.text

                        if delta:
                            await queues[index].put(delta)
            except asyncio.CancelledError:
                pass
            finally:
                await self.engine.abort(request_id)
                for index, queue in enumerate(queues):
                    if active[index]:
                        try:
                            queue.put_nowait(end)
                        except asyncio.QueueFull:
                            # Drop a pending chunk to guarantee the terminator lands.
                            try:
                                queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                            queue.put_nowait(end)

        fan_out_task = asyncio.create_task(_fan_out_sequences())

        async def _stream(index: int, queue: asyncio.Queue) -> AsyncIterator[str]:
            try:
                while True:
                    chunk = await queue.get()
                    if chunk is end:
                        return
                    yield chunk
            finally:
                active[index] = False
                if not any(active) and not fan_out_task.done():
                    fan_out_task.cancel()

        return [ _stream(index, queue) for index, queue in enumerate(queues) ]

@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.VLLM)
class VllmTextGenerationTaskService(VllmModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await VllmTextGenerationTaskAction(action, self.engine).run(context)
