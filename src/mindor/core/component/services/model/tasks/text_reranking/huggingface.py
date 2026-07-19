from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import HuggingfaceTextRerankingModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextRerankingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from .common import TextRerankingTaskAction
import asyncio

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
        }

        if params["max_input_length"] is not None:
            tokenizer_params["max_length"] = params["max_input_length"]

        params["tokenizer"] = tokenizer_params

        return params

    async def _rerank(
        self,
        queries: List[str],
        documents: List[List[str]],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[List[float]]:
        import torch

        pairs: List[Tuple[str, str]] = []
        offsets: List[int] = []
        for query, texts in zip(queries, documents):
            offsets.append(len(pairs))
            pairs.extend((query, text) for text in texts)

        inputs: Dict[str, Tensor] = self.tokenizer(pairs, **params["tokenizer"])
        inputs = { k: v.to(self.device) for k, v in inputs.items() }

        with torch.inference_mode():
            outputs: SequenceClassifierOutput = self.model(**inputs)
            logits = outputs.logits

        if logits.dim() == 2 and logits.size(-1) > 1:
            scores = logits[:, -1]
        else:
            scores = logits.view(-1)

        if params["normalize"]:
            scores = torch.sigmoid(scores)

        scores = scores.float().cpu().tolist()

        return [ scores[start:start + len(texts)] for start, texts in zip(offsets, documents) ]

@register_model_task_service(ModelTaskType.TEXT_RERANKING, ModelDriver.HUGGINGFACE)
class HuggingfaceTextRerankingTaskService(HuggingfaceLanguageModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceTextRerankingTaskAction(action, self.model, self.tokenizer, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForSequenceClassification
        return AutoModelForSequenceClassification

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
