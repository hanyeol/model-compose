from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.dsl.schema.component import HuggingfaceTextEmbeddingModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from .common import TextEmbeddingTaskAction

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from transformers.modeling_outputs import BaseModelOutput
    from torch import Tensor
    import torch

class HuggingfaceTextEmbeddingTaskAction(TextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        architecture: HuggingfaceTextEmbeddingModelArchitecture,
        model: Union[PreTrainedModel, SentenceTransformer],
        tokenizer: Optional[PreTrainedTokenizer],
        device: torch.device
    ):
        super().__init__(config)

        self.architecture: HuggingfaceTextEmbeddingModelArchitecture = architecture
        self.model: Union[PreTrainedModel, SentenceTransformer] = model
        self.tokenizer: Optional[PreTrainedTokenizer] = tokenizer
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tokenizer_params: Dict[str, Any] = {
            "return_tensors": "pt",
            "padding": True,
            "truncation": True,
            "max_length": params["max_input_length"] or self.tokenizer.model_max_length,
        }

        params["tokenizer"] = tokenizer_params

        return params

    async def _embed_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        def _embed() -> List[List[float]]:
            if self.architecture == HuggingfaceTextEmbeddingModelArchitecture.SBERT:
                return self.model.encode(texts, normalize_embeddings=bool(params.get("normalize", True))).tolist()

            import torch, torch.nn.functional as F

            inputs: Dict[str, Tensor] = self.tokenizer(texts, **params["tokenizer"])
            inputs = { key: value.to(self.device) for key, value in inputs.items() }

            with torch.inference_mode():
                outputs: BaseModelOutput = self.model(**inputs)
                last_hidden_state = outputs.last_hidden_state

            attention_mask = inputs.get("attention_mask", None)
            embeddings = self._pool_hidden_state(last_hidden_state, attention_mask, params["pooling"])

            if params["normalize"]:
                embeddings = F.normalize(embeddings, p=2, dim=1, eps=1e-12)

            return embeddings.cpu().tolist()

        return await self._run_in_executor(_embed)

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
    def get_setup_requirements(self) -> Optional[List[str]]:
        requirements = super().get_setup_requirements() or []

        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.SBERT:
            return [ *requirements, "sentence-transformers" ]

        return requirements

    async def _load_model(self) -> None:
        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.SBERT:
            from sentence_transformers import SentenceTransformer

            model_path = await self._provision_model(self.config.model)
            device = self._resolve_device(self.config.device)

            self.model = SentenceTransformer(model_path, device=str(device.type))
            self.device = device

            return

        await super()._load_model()

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.BERT:
            from transformers import BertModel
            return BertModel

        from transformers import AutoModel
        return AutoModel

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.BERT:
            from transformers import BertTokenizer
            return BertTokenizer

        from transformers import AutoTokenizer
        return AutoTokenizer

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceTextEmbeddingTaskAction(action, self.config.architecture, self.model, self.tokenizer, self.device).run(context)
