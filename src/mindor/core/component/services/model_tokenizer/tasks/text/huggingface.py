from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelTokenizerActionConfig
from mindor.dsl.schema.action.impl.model_tokenizer.tasks.common import ModelTokenizerMethod
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.array import ArrayValue
from ...base import ModelTokenizerTaskType, ModelTokenizerDriver, register_model_tokenizer_task_service
from ...base import HuggingfaceModelTokenizerTaskService, ComponentActionContext

class HuggingfaceTextModelTokenizerTaskAction:
    def __init__(self, config: ModelTokenizerActionConfig, tokenizer: Any):
        self.config: ModelTokenizerActionConfig = config
        self.tokenizer = tokenizer

    async def run(self, context: ComponentActionContext) -> Any:
        value      = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_single_input  = not isinstance(value, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(value, batch_size=batch_size or 1):
                    batch_results = self._process(self.config.method, batch_inputs, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(value, batch_size=batch_size or 1):
                batch_results = self._process(self.config.method, batch_inputs, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, method: ModelTokenizerMethod, context: ComponentActionContext) -> Any:
        if method == ModelTokenizerMethod.ENCODE:
            return await context.render_text(self.config.text)

        if method == ModelTokenizerMethod.DECODE:
            return await context.render_array(self.config.token_ids)

        if method == ModelTokenizerMethod.COUNT:
            return await context.render_text(self.config.text)

        raise ValueError(f"Unsupported tokenizer method: {method}")

    async def _resolve_params(self, method: ModelTokenizerMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == ModelTokenizerMethod.ENCODE:
            max_length         = await context.render_variable(self.config.max_length)
            padding            = await context.render_variable(self.config.padding)
            truncation         = await context.render_variable(self.config.truncation)
            additional_returns = await context.render_variable(self.config.additional_returns) or []

            encode_params: Dict[str, Any] = {}
            if max_length is not None:
                encode_params["max_length"] = int(max_length)
            if padding:
                encode_params["padding"] = "max_length" if max_length is not None else True
            if truncation:
                encode_params["truncation"] = True
            if "special_tokens_mask" in additional_returns:
                encode_params["return_special_tokens_mask"] = True
            if "offset_mapping" in additional_returns:
                encode_params["return_offsets_mapping"] = True
            if "length" in additional_returns:
                encode_params["return_length"] = True

            return {
                "encode_params":      encode_params,
                "additional_returns": additional_returns,
            }

        if method == ModelTokenizerMethod.DECODE:
            skip_special_tokens = await context.render_variable(self.config.skip_special_tokens)

            return {
                "skip_special_tokens": bool(skip_special_tokens),
            }

        if method == ModelTokenizerMethod.COUNT:
            return {}

        raise ValueError(f"Unsupported tokenizer method: {method}")

    def _process(self, method: ModelTokenizerMethod, inputs: List[Any], params: Dict[str, Any]) -> List[Any]:
        if method == ModelTokenizerMethod.ENCODE:
            return self._encode(inputs, params)

        if method == ModelTokenizerMethod.DECODE:
            return self._decode(inputs, params)

        if method == ModelTokenizerMethod.COUNT:
            return self._count(inputs, params)

        raise ValueError(f"Unsupported tokenizer method: {method}")

    def _encode(self, texts: List[str], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        outputs = self.tokenizer(texts, **params["encode_params"])

        results: List[Dict[str, Any]] = []
        for i in range(len(texts)):
            result: Dict[str, Any] = { "input_ids": outputs["input_ids"][i] }
            if "attention_mask" in outputs:
                result["attention_mask"] = outputs["attention_mask"][i]
            for key in params["additional_returns"]:
                if key in outputs:
                    result[key] = outputs[key][i]
            results.append(result)

        return results

    def _decode(self, token_ids: List[ArrayValue], params: Dict[str, Any]) -> List[Dict[str, str]]:
        outputs = self.tokenizer.batch_decode(
            [ token_ids.values for token_ids in token_ids ],
            skip_special_tokens=params["skip_special_tokens"],
        )

        return [ { "text": text } for text in outputs ]

    def _count(self, texts: List[str], params: Dict[str, Any]) -> List[Dict[str, int]]:
        outputs = self.tokenizer(texts)

        return [ { "count": len(outputs["input_ids"][i]) } for i in range(len(texts)) ]

@register_model_tokenizer_task_service(ModelTokenizerTaskType.TEXT, ModelTokenizerDriver.HUGGINGFACE)
class HuggingfaceTextModelTokenizerTaskService(HuggingfaceModelTokenizerTaskService):
    async def run(self, action: ModelTokenizerActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceTextModelTokenizerTaskAction(action, self.tokenizer).run(context)
