from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelTokenizerActionConfig
from mindor.dsl.schema.action.impl.model_tokenizer.impl.common import ModelTokenizerMethod
from ...base import ModelTokenizerTaskType, ModelTokenizerDriver, register_model_tokenizer_task_service
from ...base import HuggingfaceModelTokenizerTaskService, ComponentActionContext

class HuggingfaceTextModelTokenizerTaskAction:
    def __init__(self, config: ModelTokenizerActionConfig, tokenizer: Any):
        self.config: ModelTokenizerActionConfig = config
        self.tokenizer = tokenizer

    async def run(self, context: ComponentActionContext) -> Any:
        if self.config.method == ModelTokenizerMethod.ENCODE:
            return await self._encode(context)

        if self.config.method == ModelTokenizerMethod.DECODE:
            return await self._decode(context)

        if self.config.method == ModelTokenizerMethod.COUNT:
            return await self._count(context)

        raise ValueError(f"Unsupported tokenizer method: {self.config.method}")

    async def _encode(self, context: ComponentActionContext) -> Dict[str, Any]:
        text       = await context.render_variable(self.config.text)
        max_length = await context.render_variable(self.config.max_length)
        padding    = await context.render_variable(self.config.padding)
        truncation = await context.render_variable(self.config.truncation)

        encode_params = {}
        if max_length is not None:
            encode_params["max_length"] = int(max_length)
        if padding:
            encode_params["padding"] = "max_length" if max_length else True
        if truncation:
            encode_params["truncation"] = True

        encoded = self.tokenizer(text, **encode_params)

        return {
            "input_ids": encoded["input_ids"],
            "attention_mask": encoded["attention_mask"]
        }

    async def _decode(self, context: ComponentActionContext) -> Dict[str, str]:
        token_ids           = await context.render_variable(self.config.token_ids)
        skip_special_tokens = await context.render_variable(self.config.skip_special_tokens)

        text = self.tokenizer.decode(token_ids, skip_special_tokens=bool(skip_special_tokens))

        return { "text": text }

    async def _count(self, context: ComponentActionContext) -> Dict[str, int]:
        text = await context.render_variable(self.config.text)

        token_ids = self.tokenizer.encode(text)

        return { "count": len(token_ids) }

@register_model_tokenizer_task_service(ModelTokenizerTaskType.TEXT, ModelTokenizerDriver.HUGGINGFACE)
class HuggingfaceTextModelTokenizerTaskService(HuggingfaceModelTokenizerTaskService):
    async def run(self, action: ModelTokenizerActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceTextModelTokenizerTaskAction(action, self._tokenizer).run(context)
