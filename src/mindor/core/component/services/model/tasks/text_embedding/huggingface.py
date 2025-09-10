from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceLanguageModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from transformers.modeling_outputs import BaseModelOutput
    from torch import Tensor
    import torch

class HuggingfaceTextEmbeddingTaskAction:
    def __init__(self, config: TextEmbeddingModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer, device: torch.device):
        self.config: TextEmbeddingModelActionConfig = config
        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext) -> Any:
        import torch, torch.nn.functional as F

        text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(text, list))
        is_output_array_mode: bool = context.contains_variable_reference("result[]", self.config.output)
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        batch_size       = await context.render_variable(self.config.batch_size)
        stream           = await context.render_variable(self.config.stream)
        tokenizer_params = await self._resolve_tokenizer_params(context)
        pooling          = await context.render_variable(self.config.params.pooling)
        normalize        = await context.render_variable(self.config.params.normalize)

        async def _embed():
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                inputs: Dict[str, Tensor] = self.tokenizer(batch_texts, **tokenizer_params)
                inputs = { k: v.to(self.device) for k, v in inputs.items() }

                with torch.inference_mode():
                    outputs: BaseModelOutput = self.model(**inputs)
                    last_hidden_state = outputs.last_hidden_state # (batch_size, seq_len, hidden_size)

                attention_mask = inputs.get("attention_mask", None)
                embeddings = self._pool_hidden_state(last_hidden_state, attention_mask, pooling)

                if normalize:
                    embeddings = F.normalize(embeddings, p=2, dim=1, eps=1e-12)

                embeddings = embeddings.cpu().tolist()

                if self.config.output and is_output_array_mode:
                    rendered_outputs = []
                    for embedding in embeddings:
                        context.register_source("result[]", embedding)
                        output = await context.render_variable(self.config.output, ignore_files=True)
                        rendered_outputs.append(output)
                    yield rendered_outputs
                else:
                    yield embeddings

        if stream:
            async def _stream_output_generator():
                async for embeddings in _embed():
                    if not is_output_array_mode:
                        for embedding in embeddings:
                            context.register_source("result", embedding)
                            yield (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
                    else:
                        for embedding in embeddings:
                            yield embedding

            return _stream_output_generator()
        else:
            async for embeddings in _embed():
                results.extend(embeddings)

            if not is_output_array_mode:
                result = results[0] if is_single_input else results
                context.register_source("result", result)

                return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
            else:
                return results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    async def _resolve_tokenizer_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length)

        params = {
            "return_tensors": "pt",
            "padding": True,
            "truncation": False
        }

        if max_input_length is not None:
            params["max_length"] = max_input_length
            params["truncation"] = True

        return params

    def _pool_hidden_state(self, last_hidden_state: Tensor, attention_mask: Optional[Tensor], pooling: str) -> Tensor:
        import torch

        if pooling == "mean":
            if attention_mask is not None:
                mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size())
                summed = torch.sum(last_hidden_state * mask, dim=1)
                count = torch.clamp(mask.sum(dim=1), min=1e-9)
                return summed / count
            else:
                return torch.mean(last_hidden_state, dim=1)

        if pooling == "cls":
            return last_hidden_state[:, 0]

        if pooling == "max":
            if attention_mask is not None:
                mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size())
                last_hidden_state = last_hidden_state.masked_fill(mask == 0, -1e9)
            return torch.max(last_hidden_state, dim=1).values

        raise ValueError(f"Unsupported pooling type: {pooling}")

@register_model_task_service(ModelTaskType.TEXT_EMBEDDING, ModelDriver.HUGGINGFACE)
class HuggingfaceTextEmbeddingTaskService(HuggingfaceLanguageModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await HuggingfaceTextEmbeddingTaskAction(action, self.model, self.tokenizer, self.device).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModel
        return AutoModel

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
