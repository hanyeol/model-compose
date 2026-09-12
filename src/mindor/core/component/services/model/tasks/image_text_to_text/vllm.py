from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ImageTextToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from .common import ImageTextToTextTaskAction
from PIL import Image as PILImage
import asyncio, ulid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine, SamplingParams
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

_STREAM_QUEUE_SIZE = 32

class VllmImageTextToTextTaskAction(ImageTextToTextTaskAction):
    def __init__(
        self,
        config: ImageTextToTextModelActionConfig,
        engine: AsyncLLMEngine,
        tokenizer: PreTrainedTokenizerBase,
    ):
        super().__init__(config)

        self.engine: AsyncLLMEngine = engine
        self.tokenizer: PreTrainedTokenizerBase = tokenizer

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
        messages: List[List[Dict[str, Any]]],
        images: List[List[PILImage.Image]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[List[str]], List[List[AsyncIterator[str]]]]:
        num_return_sequences = params["num_return_sequences"] or 1

        prompts = [
            self.tokenizer.apply_chat_template(single_messages, tokenize=False, add_generation_prompt=True)
            for single_messages in messages
        ]

        if streaming:
            return [
                self._stream_text(prompt, prompt_images, params["sampling"], num_return_sequences, cancellation_token)
                for prompt, prompt_images in zip(prompts, images)
            ]

        return [
            await self._generate_text(prompt, prompt_images, params["sampling"], num_return_sequences, cancellation_token)
            for prompt, prompt_images in zip(prompts, images)
        ]

    async def _generate_text(
        self,
        prompt: str,
        images: List[PILImage.Image],
        sampling: SamplingParams,
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[str]:
        request_id = f"request-{ulid.ulid()}"
        texts: List[str] = [ "" ] * num_return_sequences
        request = { "prompt": prompt, "multi_modal_data": { "image": images } }

        async for output in self.engine.generate(request, sampling, request_id=request_id):
            if cancellation_token is not None and cancellation_token.is_cancelled():
                await self.engine.abort(request_id)
                break

            for sequence in output.outputs:
                texts[sequence.index] = sequence.text

        return texts

    def _stream_text(
        self,
        prompt: str,
        images: List[PILImage.Image],
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
        request = { "prompt": prompt, "multi_modal_data": { "image": images } }
        queues: List[asyncio.Queue] = [ asyncio.Queue(maxsize=_STREAM_QUEUE_SIZE) for _ in range(num_return_sequences) ]
        active = [ True ] * num_return_sequences
        end_of_stream = object()

        async def _fan_out_sequences():
            previous = [ "" ] * num_return_sequences

            try:
                async for output in self.engine.generate(request, sampling, request_id=request_id):
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

    def _build_messages(self, prompt: str, image_count: int, system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []

        if system_prompt:
            messages.append({ "role": "system", "content": system_prompt })

        messages.append({
            "role": "user",
            "content": [ *[ { "type": "image" } for _ in range(image_count) ], { "type": "text", "text": prompt } ],
        })

        return messages

@register_model_task_service(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriver.VLLM)
class VllmImageTextToTextTaskService(VllmModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await VllmImageTextToTextTaskAction(action, self.engine, self.tokenizer).run(context)
