from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from .common import TextEmbeddingTaskAction
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from transformers.modeling_outputs import BaseModelOutput
    from torch import Tensor
    import torch

class HuggingfaceTextEmbeddingTaskAction(TextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device
    ):
        super().__init__(config)

        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tokenizer_params: Dict[str, Any] = {
            "return_tensors": "pt",
            "padding": True,
            "truncation": False,
        }

        if params["max_input_length"] is not None:
            tokenizer_params["max_length"] = params["max_input_length"]
            tokenizer_params["truncation"] = True

        params["tokenizer"] = tokenizer_params

        return params

    async def _embed(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[List[float]]:
        import torch, torch.nn.functional as F

        inputs: Dict[str, Tensor] = self.tokenizer(texts, **params["tokenizer"])
        inputs = { k: v.to(self.device) for k, v in inputs.items() }

        with torch.inference_mode():
            outputs: BaseModelOutput = self.model(**inputs)
            last_hidden_state = outputs.last_hidden_state

        attention_mask = inputs.get("attention_mask", None)
        embeddings = self._pool_hidden_state(last_hidden_state, attention_mask, params["pooling"])

        if params["normalize"]:
            embeddings = F.normalize(embeddings, p=2, dim=1, eps=1e-12)

        return embeddings.cpu().tolist()

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
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceTextEmbeddingTaskAction(action, self.model, self.tokenizer, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModel
        return AutoModel

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
