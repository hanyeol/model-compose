from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceTextGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import VllmModelTaskDriver, ComponentActionContext
from .common import TextGenerationTaskAction
import asyncio, ulid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine, SamplingParams

_STREAM_QUEUE_SIZE = 32

class VllmTextGenerationTaskAction(TextGenerationTaskAction):
    config: HuggingfaceTextGenerationModelActionConfig

    def __init__(
        self,
        config: HuggingfaceTextGenerationModelActionConfig,
        engine: AsyncLLMEngine,
        stream_interval: int = 1,
    ):
        super().__init__(config)

        self.engine: AsyncLLMEngine = engine
        self.stream_interval: int = max(1, stream_interval)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        from vllm import SamplingParams

        params = await super()._resolve_params(context)

        num_return_sequences = await context.render_variable(self.config.num_return_sequences)
        stop_sequences       = await context.render_variable(self.config.stop_sequences)
        do_sample            = await context.render_variable(self.config.params.do_sample)
        temperature          = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k                = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p                = await context.render_variable(self.config.params.top_p) if do_sample else None

        if params["max_input_length"] is not None:
            logging.warning("vLLM backend does not support max_input_length; ignoring configured value %r.", params["max_input_length"])

        sampling_params: Dict[str, Any] = { "n": num_return_sequences }

        if params["max_output_length"] is not None:
            sampling_params["max_tokens"] = params["max_output_length"]

        if params["min_output_length"] and params["min_output_length"] > 1:
            sampling_params["min_tokens"] = params["min_output_length"]

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
            sampling_params["stop"] = stop_sequences if isinstance(stop_sequences, list) else [ stop_sequences ]

        params.update({
            "num_return_sequences": num_return_sequences,
            "sampling":             SamplingParams(**sampling_params),
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
        sampling: SamplingParams,
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[str]:
        request_id = f"request-{ulid.ulid()}"
        texts: List[str] = [ "" ] * num_return_sequences

        async def _generate_sequences() -> None:
            async for output in self.engine.generate(prompt, sampling, request_id=request_id):
                for sequence in output.outputs:
                    texts[sequence.index] = sequence.text

        generate_task = asyncio.create_task(_generate_sequences())
        watcher_task: Optional[asyncio.Task] = None

        if cancellation_token is not None:
            async def _watch_cancellation() -> None:
                while not cancellation_token.is_cancelled():
                    if generate_task.done():
                        return

                    await asyncio.sleep(0.2)

                await self.engine.abort(request_id)

            watcher_task = asyncio.create_task(_watch_cancellation())

        try:
            await generate_task
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()

                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

        return texts

    async def _stream_text(
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
        from vllm.sampling_params import RequestOutputKind

        request_id = f"request-{ulid.ulid()}"
        queues: List[asyncio.Queue] = [ asyncio.Queue(maxsize=_STREAM_QUEUE_SIZE) for _ in range(num_return_sequences) ]
        active = [ True ] * num_return_sequences
        end_of_stream = object()

        async def _generate_sequences():
            # AsyncLLMEngine.generate() bypasses OutputProcessor, so we
            # replicate its stream_interval batching here: hold deltas until
            # `stream_interval` new tokens have accumulated, or the sequence
            # finishes, or it's the first emit — mirrors
            # vllm/v1/engine/output_processor.py:RequestState.make_request_output.
            pending_delta = [ "" ] * num_return_sequences
            pending_tokens = [ 0 ] * num_return_sequences
            emitted_once = [ False ] * num_return_sequences

            # Switch to DELTA so each engine emission carries only the newly
            # generated tokens. vLLM's CUMULATIVE default sends the whole running
            # text per step, which also forces per-token flush even when
            # stream_interval > 1 (vllm-project/vllm#60547).
            sampling.output_kind = RequestOutputKind.DELTA

            try:
                async for output in self.engine.generate(prompt, sampling, request_id=request_id):
                    if not any(active):
                        break

                    finished = output.finished

                    for sequence in output.outputs:
                        index = sequence.index

                        if not active[index]:
                            continue

                        if sequence.text:
                            pending_delta[index] += sequence.text
                            pending_tokens[index] += len(sequence.token_ids)

                        should_emit = (
                            finished
                            or not emitted_once[index]
                            or pending_tokens[index] >= self.stream_interval
                        )

                        if should_emit and pending_delta[index]:
                            await queues[index].put(pending_delta[index])
                            pending_delta[index] = ""
                            pending_tokens[index] = 0
                            emitted_once[index] = True
            except asyncio.CancelledError:
                pass
            finally:
                await self.engine.abort(request_id)

                for index, queue in enumerate(queues):
                    if active[index]:
                        # Flush whatever didn't reach the interval threshold.
                        if pending_delta[index]:
                            try:
                                queue.put_nowait(pending_delta[index])
                            except asyncio.QueueFull:
                                pass

                        try:
                            queue.put_nowait(end_of_stream)
                        except asyncio.QueueFull:
                            # Drop a pending chunk to guarantee the terminator lands.
                            try:
                                queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass

                            queue.put_nowait(end_of_stream)

        generate_task = asyncio.create_task(_generate_sequences())
        watcher_task: Optional[asyncio.Task] = None

        if cancellation_token is not None:
            async def _watch_cancellation() -> None:
                while not cancellation_token.is_cancelled():
                    if generate_task.done():
                        return

                    await asyncio.sleep(0.2)

                await self.engine.abort(request_id)

            watcher_task = asyncio.create_task(_watch_cancellation())

        async def _stream(index: int, queue: asyncio.Queue) -> AsyncIterator[str]:
            try:
                while True:
                    chunk = await queue.get()

                    if chunk is end_of_stream:
                        return

                    yield chunk
            finally:
                active[index] = False

                if not any(active):
                    if not generate_task.done():
                        generate_task.cancel()

                    if watcher_task is not None and not watcher_task.done():
                        watcher_task.cancel()

                        try:
                            await watcher_task
                        except (asyncio.CancelledError, Exception):
                            pass

        return [ _stream(index, queue) for index, queue in enumerate(queues) ]

@register_model_task_driver(ModelTaskType.TEXT_GENERATION, ModelDriverType.VLLM)
class VllmTextGenerationTaskDriver(VllmModelTaskDriver):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await VllmTextGenerationTaskAction(
            action,
            self.engine,
            self.engine_args.stream_interval or 1,
        ).run(context)
