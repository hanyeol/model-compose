from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import HuggingfaceTextRerankingModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextRerankingModelActionConfig
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskDriver
from .common import TextRerankingTaskAction

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from transformers.modeling_outputs import SequenceClassifierOutput
    from torch import Tensor
    import torch

class HuggingfaceTextRerankingTaskAction(TextRerankingTaskAction):
    def __init__(
        self,
        config: TextRerankingModelActionConfig,
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
            "truncation": True,
            "max_length": params["max_input_length"] or self.tokenizer.model_max_length,
        }

        params["tokenizer"] = tokenizer_params

        return params

    async def _rerank(
        self,
        query: str,
        texts: TextArrayValue,
        batch_size: int,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[float]:
        texts = await texts.collect()
        pairs: List[Tuple[str, str]] = [ (query, text) for text in texts ]

        def _rerank() -> List[float]:
            import torch

            scores: List[float] = []

            for start in range(0, len(pairs), batch_size):
                inputs: Dict[str, Tensor] = self.tokenizer(pairs[start:start + batch_size], **params["tokenizer"])
                inputs = { key: value.to(self.device) for key, value in inputs.items() }

                with torch.inference_mode():
                    outputs: SequenceClassifierOutput = self.model(**inputs)
                    logits = outputs.logits

                if logits.dim() == 2 and logits.size(-1) > 1:
                    chunk_scores = logits[:, -1]
                else:
                    chunk_scores = logits.view(-1)

                if params["normalize"]:
                    chunk_scores = torch.sigmoid(chunk_scores)

                scores.extend(chunk_scores.float().cpu().tolist())

            return scores

        return await self._run_in_executor(_rerank)

@register_model_task_driver(ModelTaskType.TEXT_RERANKING, ModelDriverType.HUGGINGFACE)
class HuggingfaceTextRerankingTaskDriver(HuggingfaceLanguageModelTaskDriver):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForSequenceClassification
        return AutoModelForSequenceClassification

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceTextRerankingTaskAction(
            action,
            self.model,
            self.tokenizer,
            self.device
        ).run(context)
