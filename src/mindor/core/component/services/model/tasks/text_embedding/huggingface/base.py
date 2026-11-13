from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from ..common import TextEmbeddingTaskAction

if TYPE_CHECKING:
    from torch import Tensor
    import torch

class HuggingfaceTextEmbeddingTaskAction(TextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        device: torch.device,
    ):
        super().__init__(config)

        self.device: torch.device = device

    def _resolve_text_features(self, features: Any, attention_mask: Optional[Tensor], pooling: str) -> Tensor:
        # transformers 5.x returns BaseModelOutputWithPooling from get_text_features;
        # older versions return a bare tensor. Handle both.
        import torch

        if isinstance(features, torch.Tensor):
            return features

        if getattr(features, "pooler_output", None) is not None:
            return features.pooler_output

        if getattr(features, "last_hidden_state", None) is not None:
            return self._pool_hidden_state(features.last_hidden_state, attention_mask, pooling)

        raise ValueError(f"Cannot extract text features from output of type {type(features).__name__}")

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
