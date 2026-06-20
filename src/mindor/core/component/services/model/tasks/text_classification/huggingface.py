from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.component import HuggingfaceTextClassificationModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextClassificationModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from .common import TextClassificationTaskAction
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    from transformers.modeling_outputs import SequenceClassifierOutput
    from torch import Tensor
    import torch

class HuggingfaceTextClassificationTaskAction(TextClassificationTaskAction):
    def __init__(
        self,
        config: TextClassificationModelActionConfig,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device,
        labels: Optional[List[str]]
    ):
        super().__init__(config, labels)

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

    async def _predict(self, texts: List[str], params: Dict[str, Any], labels: Optional[List[str]], loop: asyncio.AbstractEventLoop) -> List[Any]:
        import torch, torch.nn.functional as F

        inputs: Dict[str, Tensor] = self.tokenizer(texts, **params["tokenizer"])
        inputs = { k: v.to(self.device) for k, v in inputs.items() }

        with torch.inference_mode():
            outputs: SequenceClassifierOutput = self.model(**inputs)
            logits = outputs.logits

        predictions = []

        if params["return_probabilities"]:
            probs = F.softmax(logits, dim=-1).cpu()
            for prob in probs:
                predicted_index = torch.argmax(prob).item()
                predictions.append({
                    "label":         labels[predicted_index] if labels else predicted_index,
                    "probabilities": prob.tolist(),
                })
        else:
            predicted_indices = torch.argmax(logits, dim=-1).tolist()
            for predicted_index in predicted_indices:
                predictions.append(labels[predicted_index] if labels else predicted_index)

        return predictions

@register_model_task_service(ModelTaskType.TEXT_CLASSIFICATION, ModelDriver.HUGGINGFACE)
class HuggingfaceTextClassificationTaskService(HuggingfaceLanguageModelTaskService):
    def __init__(self, id: str, config: HuggingfaceTextClassificationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.labels: Optional[List[str]] = config.labels

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceTextClassificationTaskAction(action, self.model, self.tokenizer, self.device, self.labels).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForSequenceClassification
        return AutoModelForSequenceClassification

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
