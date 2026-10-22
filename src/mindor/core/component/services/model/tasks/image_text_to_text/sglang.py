from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ImageTextToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import SglangModelTaskDriver, ComponentActionContext
from .common import ImageTextToTextTaskAction
from PIL import Image as PILImage
import asyncio, base64, io, ulid

if TYPE_CHECKING:
    from sglang import Engine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

_STREAM_QUEUE_SIZE = 32

class SglangImageTextToTextTaskAction(ImageTextToTextTaskAction):
    def __init__(
        self,
        config: ImageTextToTextModelActionConfig,
        engine: Engine,
        tokenizer: PreTrainedTokenizerBase,
    ):
        super().__init__(config)

        self.engine: Engine = engine
        self.tokenizer: PreTrainedTokenizerBase = tokenizer

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        if params["max_input_length"] is not None:
            logging.warning("SGLang backend does not support max_input_length; ignoring configured value %r.", params["max_input_length"])

        sampling_params: Dict[str, Any] = { "n": params["num_return_sequences"] }

        if params["max_output_length"] is not None:
            sampling_params["max_new_tokens"] = params["max_output_length"]

        if params["min_output_length"] and params["min_output_length"] > 1:
            sampling_params["min_new_tokens"] = params["min_output_length"]

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

        repetition_penalty = await context.render_variable(self.config.params.repetition_penalty)

        if repetition_penalty is not None:
            sampling_params["repetition_penalty"] = repetition_penalty

        no_repeat_ngram_size = await context.render_variable(self.config.params.no_repeat_ngram_size)

        if no_repeat_ngram_size is not None:
            logging.warning("SGLang backend does not support no_repeat_ngram_size; ignoring configured value %r.", no_repeat_ngram_size)

        params["sampling"] = sampling_params

        return params

    async def _generate_batch(
        self,
        prompts: List[str],
        images: List[Optional[ImageArrayValue]],
        system_prompt: Optional[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[List[str]], List[List[AsyncIterator[str]]]]:
        num_return_sequences = params["num_return_sequences"] or 1
        images = [ (await item.collect() if item is not None else []) for item in images ]

        if streaming:
            return [
                await self._stream_text(prompts[index], images[index], system_prompt, params["sampling"], num_return_sequences, cancellation_token)
                for index in range(len(prompts))
            ]

        return [
            await self._generate_text(prompts[index], images[index], system_prompt, params["sampling"], num_return_sequences, cancellation_token)
            for index in range(len(prompts))
        ]

    async def _generate_text(
        self,
        prompt: str,
        images: List[PILImage.Image],
        system_prompt: Optional[str],
        sampling: Dict[str, Any],
        num_return_sequences: int,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[str]:
        prompt, images = await self._run_in_executor(self._prepare_request, prompt, images, system_prompt)

        request_id = f"request-{ulid.ulid()}"
        texts: List[str] = [ "" ] * num_return_sequences

        outputs = await self.engine.async_generate(
            prompt,
            sampling,
            stream=False,
            rid=request_id,
            image_data=images,
        )

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
        images: List[PILImage.Image],
        system_prompt: Optional[str],
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
        prompt, images = await self._run_in_executor(self._prepare_request, prompt, images, system_prompt)

        request_id = f"request-{ulid.ulid()}"
        queues: List[asyncio.Queue] = [ asyncio.Queue(maxsize=_STREAM_QUEUE_SIZE) for _ in range(num_return_sequences) ]
        active = [ True ] * num_return_sequences
        end_of_stream = object()

        async def _fan_out_sequences():
            previous = [ "" ] * num_return_sequences

            try:
                async for output in await self.engine.async_generate(
                    prompt,
                    sampling,
                    stream=True,
                    rid=request_id,
                    image_data=images,
                ):
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

    def _prepare_request(
        self,
        prompt: str,
        images: List[PILImage.Image],
        system_prompt: Optional[str],
    ) -> tuple[str, Optional[List[str]]]:
        messages = self._build_messages(prompt, len(images), system_prompt)
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images = self._encode_images(images) if images else None

        return prompt, images

    def _build_messages(self, prompt: str, image_count: int, system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []

        if system_prompt:
            messages.append({ "role": "system", "content": system_prompt })

        messages.append({
            "role": "user",
            "content": [ *[ { "type": "image" } for _ in range(image_count) ], { "type": "text", "text": prompt } ],
        })

        return messages

    def _encode_images(self, images: List[PILImage.Image]) -> List[str]:
        # SGLang accepts images as base64 strings, file paths, or URLs; model-compose
        # callers pass PIL images (see ImageTextToTextTaskAction._generate_batch).
        return [ self._to_data_uri(image) for image in images ]

    def _to_data_uri(self, image: PILImage.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

@register_model_task_driver(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriverType.SGLANG)
class SglangImageTextToTextTaskDriver(SglangModelTaskDriver):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SglangImageTextToTextTaskAction(action, self.engine, self.tokenizer).run(context)
