from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any, Iterator
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ImageTextToTextModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from .common import ImageTextToTextTaskAction
from PIL import Image as PILImage
import asyncio, ulid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine, SamplingParams
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

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

    def _build_chat_prompt(self, prompt_text: str, system_prompt: Optional[str]) -> str:
        messages: List[Dict[str, Any]] = []

        if system_prompt:
            messages.append({ "role": "system", "content": system_prompt })

        messages.append({
            "role": "user",
            "content": [
                { "type": "image" },
                { "type": "text", "text": prompt_text },
            ],
        })

        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    async def _generate(
        self,
        images: List[PILImage.Image],
        prompts: List[str],
        system_prompt: Optional[str],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        sampling = params["sampling"]

        pairs: List[tuple[str, PILImage.Image]] = []
        for image, prompt in zip(images, prompts):
            chat_prompt = self._build_chat_prompt(prompt, system_prompt)
            pairs.append((chat_prompt, image))

        if streaming:
            return [ self._stream_one(chat_prompt, image, sampling) for chat_prompt, image in pairs ]

        return [ await self._generate_one(chat_prompt, image, sampling) for chat_prompt, image in pairs ]

    async def _generate_one(self, chat_prompt: str, image: PILImage.Image, sampling: SamplingParams) -> str:
        request_id = f"request-{ulid.ulid()}"
        text = ""
        request = { "prompt": chat_prompt, "multi_modal_data": { "image": image } }
        async for output in self.engine.generate(request, sampling, request_id=request_id):
            if output.outputs:
                text = output.outputs[0].text
        return text

    async def _stream_one(self, chat_prompt: str, image: PILImage.Image, sampling: SamplingParams) -> AsyncIterator[str]:
        request_id = f"request-{ulid.ulid()}"
        previous = ""
        request = { "prompt": chat_prompt, "multi_modal_data": { "image": image } }
        async for output in self.engine.generate(request, sampling, request_id=request_id):
            text = output.outputs[0].text if output.outputs else ""
            delta = text[len(previous):]
            previous = text
            if delta:
                yield delta

@register_model_task_service(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriver.VLLM)
class VllmImageTextToTextTaskService(VllmModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        return await VllmImageTextToTextTaskAction(action, self.engine, self.tokenizer).run(context, loop)
