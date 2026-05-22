from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextClassificationModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceLanguageModelTaskService, ComponentActionContext
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
        device: torch.device
    ):
        super().__init__(config)

        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def _predict(self, texts: List[str], labels: Optional[List[str]], context: ComponentActionContext) -> List[Any]:
        import torch, torch.nn.functional as F

        tokenizer_params     = await self._resolve_tokenizer_params(context)
        return_probabilities = await context.render_variable(self.config.params.return_probabilities)

        inputs: Dict[str, Tensor] = self.tokenizer(texts, **tokenizer_params)
        inputs = { k: v.to(self.device) for k, v in inputs.items() }

        with torch.inference_mode():
            outputs: SequenceClassifierOutput = self.model(**inputs)
            logits = outputs.logits

        predictions = []

        if return_probabilities:
            probs = F.softmax(logits, dim=-1).cpu()
            for prob in probs:
                predicted_index = torch.argmax(prob).item()
                predictions.append({
                    "label": labels[predicted_index] if labels else predicted_index,
                    "probabilities": prob.tolist()
                })
        else:
            predicted_indices = torch.argmax(logits, dim=-1).tolist()
            for predicted_index in predicted_indices:
                predictions.append(labels[predicted_index] if labels else predicted_index)

        return predictions

    async def _resolve_tokenizer_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length)

        params: Dict[str, Any] = {
            "return_tensors": "pt",
            "padding": True,
            "truncation": False
        }

        if max_input_length is not None:
            params["max_length"] = max_input_length
            params["truncation"] = True

        return params

@register_model_task_service(ModelTaskType.TEXT_CLASSIFICATION, ModelDriver.HUGGINGFACE)
class HuggingfaceTextClassificationTaskService(HuggingfaceLanguageModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceTextClassificationTaskAction(action, self.model, self.tokenizer, self.device).run(context, self.config.labels)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForSequenceClassification
        return AutoModelForSequenceClassification

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
