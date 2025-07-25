from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextClassificationModelActionConfig
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer
from transformers.modeling_outputs import SequenceClassifierOutput
import torch.nn.functional as F
import torch

class TextClassificationTaskAction:
    def __init__(self, config: TextClassificationModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer):
        self.config: TextClassificationModelActionConfig = config
        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer

    async def run(self, context: ComponentActionContext, labels: Optional[List[str]]) -> Any:
        text: Union[str, List[str]] = await context.render_variable(self.config.text)

        return_probabilities = await context.render_variable(self.config.params.return_probabilities)
        batch_size           = await context.render_variable(self.config.params.batch_size)

        texts: List[str] = [ text ] if isinstance(text, str) else text
        results = []

        for index in range(0, len(texts), batch_size):
            batch_texts = texts[index:index + batch_size]
            inputs = self.tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True).to(self.model.device)

            with torch.no_grad():
                outputs: SequenceClassifierOutput = self.model(**inputs)
                logits = outputs.logits  # shape: (batch_size, num_classes)
                
                predicted = []
                if return_probabilities:
                    probs = F.softmax(logits, dim=-1).cpu()
                    for prob in probs:
                        predicted_index = torch.argmax(prob).item()
                        predicted.append({
                            "label": labels[predicted_index] if labels else predicted_index,
                            "probabilities": prob.tolist()
                        })
                else:
                    predicted_indices = torch.argmax(logits, dim=-1).tolist()
                    for predicted_index in predicted_indices:
                        predicted.append(labels[predicted_index] if labels else predicted_index)

            results.extend(predicted)

        result = results if len(results) > 1 else results[0]
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

@register_model_task_service(ModelTaskType.TEXT_CLASSIFICATION)
class TextClassificationTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None

    async def _serve(self) -> None:
        try:
            self.model = AutoModelForSequenceClassification.from_pretrained(self.config.model).to(torch.device(self.config.device))
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model, use_fast=self.config.fast_tokenizer)
            logging.info(f"Model and tokenizer loaded successfully on device '{self.config.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.tokenizer = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await TextClassificationTaskAction(action, self.model, self.tokenizer).run(context, self.config.labels)
