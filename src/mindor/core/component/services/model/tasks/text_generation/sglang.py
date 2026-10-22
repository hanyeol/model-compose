from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceTextGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import SglangModelTaskDriver, ComponentActionContext
from .common import TextGenerationTaskAction
import asyncio, ulid

if TYPE_CHECKING:
    from sglang import Engine

_STREAM_QUEUE_SIZE = 32

class SglangTextGenerationTaskAction(TextGenerationTaskAction):
    def __init__(
        self,
        config: HuggingfaceTextGenerationModelActionConfig,
        engine: Engine,
    ):
        super().__init__(config)

        self.engine: Engine = engine

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        num_return_sequences = await context.render_variable(self.config.num_return_sequences)
        stop_sequences       = await context.render_variable(self.config.stop_sequences)
        do_sample            = await context.render_variable(self.config.params.do_sample)
        temperature          = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k                = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p                = await context.render_variable(self.config.params.top_p) if do_sample else None

        if params["max_input_length"] is not None:
            logging.warning("SGLang backend does not support max_input_length; ignoring configured value %r.", params["max_input_length"])

        sampling_params: Dict[str, Any] = { "n": num_return_sequences }

        if params["max_output_length"] is not None:
            sampling_params["max_new_tokens"] = params["max_output_length"]

        if params["min_output_length"] and params["min_output_length"] > 1:
            sampling_params["min_new_tokens"] = params["min_output_length"]

        if do_sample:
            if temperature is not None:
                sampling_params["temperature"] = temperature

            if top_k is not None:
                sampling_params["top_k"] = top_k

            if top_p is not None:
                sampling_params["top_p"] = top_p
        else:
            sampling_params["temperature"] = 0.0

        if stop_sequences:
            sampling_params["stop"] = stop_sequences if isinstance(stop_sequences, list) else [stop_sequences]

        params.update({
            "num_return_sequences": num_return_sequences,
            "sampling":             sampling_params,
        })

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
                await self._stream_text(prompt, params["sampling"], num_return_sequences, cancellation_token)
                for prompt in texts
            ]

        return [
            await self._generate_text(prompt, params["sampling"], num_return_sequences, cancellation_token)
            for prompt in texts
        ]

    async def _generate_text(
        self,
        prompt: str,
        sampling: Dict[str, Any],
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[str]:
        request_id = f"request-{ulid.ulid()}"
        texts: List[str] = [ "" ] * num_return_sequences

        outputs = await self.engine.async_generate(prompt, sampling, stream=False, rid=request_id)

        if cancellation_token is not None and cancellation_token.is_cancelled():
            self.engine.abort_request(request_id)
            return texts

        if num_return_sequences == 1 and isinstance(outputs, dict):
            outputs = [ outputs ]

        for output in outputs:
            index = output.get("index", 0)
            texts[index] = output["text"]

        return texts

    async def _stream_text(
        self,
        prompt: str,
        sampling: Dict[str, Any],
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AsyncIterator[str]]:
        # SGLang interleaves every sequence's cumulative text in one shared
        # async iterator (tagged by `index`), so fan it out into n independent
        # per-sequence queues so each returned iterator can be consumed on its
        # own. Queues are bounded to apply backpressure on the engine when
        # consumers are slow, and the fan-out task is aborted if any consumer
        # stops early.
        request_id = f"request-{ulid.ulid()}"
        queues: List[asyncio.Queue] = [ asyncio.Queue(maxsize=_STREAM_QUEUE_SIZE) for _ in range(num_return_sequences) ]
        active = [ True ] * num_return_sequences
        end_of_stream = object()

        async def _fan_out_sequences():
            previous = [ "" ] * num_return_sequences

            try:
                async for output in await self.engine.async_generate(prompt, sampling, stream=True, rid=request_id):
                    if cancellation_token is not None and cancellation_token.is_cancelled():
                        break

                    if not any(active):
                        break

                    index = output.get("index", 0)

                    if not active[index]:
                        continue

                    delta = output["text"][len(previous[index]):]
                    previous[index] = output["text"]

                    if delta:
                        await queues[index].put(delta)
            except asyncio.CancelledError:
                pass
            finally:
                self.engine.abort_request(request_id)
                for index, queue in enumerate(queues):
                    if active[index]:
                        try:
                            queue.put_nowait(end_of_stream)
                        except asyncio.QueueFull:
                            # Drop a pending chunk to guarantee the terminator lands.
                            try:
                                queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                            queue.put_nowait(end_of_stream)

        fan_out_task = asyncio.create_task(_fan_out_sequences())

        async def _stream(index: int, queue: asyncio.Queue) -> AsyncIterator[str]:
            try:
                while True:
                    chunk = await queue.get()
                    if chunk is end_of_stream:
                        return
                    yield chunk
            finally:
                active[index] = False
                if not any(active) and not fan_out_task.done():
                    fan_out_task.cancel()

        return [ _stream(index, queue) for index, queue in enumerate(queues) ]

@register_model_task_driver(ModelTaskType.TEXT_GENERATION, ModelDriverType.SGLANG)
class SglangTextGenerationTaskDriver(SglangModelTaskDriver):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SglangTextGenerationTaskAction(action, self.engine).run(context)
