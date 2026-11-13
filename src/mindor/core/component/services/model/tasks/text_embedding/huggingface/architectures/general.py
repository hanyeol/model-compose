from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.dsl.schema.component import HuggingfaceTextEmbeddingModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from .....base import ModelTaskType, ModelDriverType, register_model_task_driver
from .....base import ComponentActionContext
from .....base.huggingface.language import HuggingfaceLanguageModelTaskDriver
from ..base import HuggingfaceTextEmbeddingTaskAction
from ...common import TextEmbedding

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from transformers.modeling_outputs import BaseModelOutput
    from torch import Tensor
    import torch

_PROJECTED_TEXT_ARCHITECTURES = {
    HuggingfaceTextEmbeddingModelArchitecture.CLIP,
    HuggingfaceTextEmbeddingModelArchitecture.SIGLIP,
    HuggingfaceTextEmbeddingModelArchitecture.XCLIP,
}

class GeneralHuggingfaceTextEmbeddingTaskAction(HuggingfaceTextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        architecture: HuggingfaceTextEmbeddingModelArchitecture,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.architecture: HuggingfaceTextEmbeddingModelArchitecture = architecture
        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer

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
    ) -> List[TextEmbedding]:
        import torch.nn.functional as F
        import torch

        def _embed() -> List[TextEmbedding]:
            inputs: Dict[str, Tensor] = self.tokenizer(texts, **params["tokenizer"])
            inputs = { key: value.to(self.device) for key, value in inputs.items() }

            with torch.inference_mode():
                if self.architecture in _PROJECTED_TEXT_ARCHITECTURES:
                    # CLIP-family models expose paired text/vision projections
                    # into a shared space via get_text_features; the projection
                    # already collapses the sequence into a single vector, so
                    # skip pooling.
                    embeddings = self._resolve_text_features(
                        self.model.get_text_features(**inputs),
                        inputs.get("attention_mask", None),
                        params["pooling"],
                    )
                else:
                    outputs: BaseModelOutput = self.model(**inputs)
                    embeddings = self._pool_hidden_state(
                        outputs.last_hidden_state,
                        inputs.get("attention_mask", None),
                        params["pooling"],
                    )

            if params["normalize"]:
                embeddings = F.normalize(embeddings, p=2, dim=1, eps=1e-12)

            return [ TextEmbedding(vector) for vector in embeddings.cpu().tolist() ]

        return await self._run_in_executor(_embed)

class GeneralHuggingfaceTextEmbeddingTaskDriver(HuggingfaceLanguageModelTaskDriver):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.BERT:
            from transformers import BertModel
            return BertModel

        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.CLIP:
            from transformers import CLIPModel
            return CLIPModel

        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.SIGLIP:
            from transformers import SiglipModel
            return SiglipModel

        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.XCLIP:
            from transformers import XCLIPModel
            return XCLIPModel

        from transformers import AutoModel
        return AutoModel

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        if self.config.architecture == HuggingfaceTextEmbeddingModelArchitecture.BERT:
            from transformers import BertTokenizer
            return BertTokenizer

        from transformers import AutoTokenizer
        return AutoTokenizer

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await GeneralHuggingfaceTextEmbeddingTaskAction(
            action,
            self.config.architecture,
            self.model,
            self.tokenizer,
            self.device,
        ).run(context)
