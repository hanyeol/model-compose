from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextClassificationModelActionConfig
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer
from transformers.modeling_outputs import SequenceClassifierOutput
import torch.nn.functional as F
from torch import Tensor
import torch, asyncio

class TextClassificationTaskAction:
    def __init__(self, config: TextClassificationModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer, device: torch.device):
        self.config: TextClassificationModelActionConfig = config
        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext, labels: Optional[List[str]]) -> Any:
        text: Union[str, List[str]] = await context.render_variable(self.config.text)

        return_probabilities = await context.render_variable(self.config.params.return_probabilities)
        batch_size           = await context.render_variable(self.config.params.batch_size)
        stream               = await context.render_variable(self.config.stream)

        is_single_input: bool = bool(not isinstance(text, list))
        is_output_array_mode: bool = context.contains_variable_reference("result[]", self.config.output)
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        async def _predict():
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                inputs: Dict[str, Tensor] = self.tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True)
                inputs = { k: v.to(self.device) for k, v in inputs.items() }

                with torch.inference_mode():
                    outputs: SequenceClassifierOutput = self.model(**inputs)
                    logits = outputs.logits # shape: (batch_size, num_classes)
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

                if self.config.output and is_output_array_mode:
                    rendered_outputs = []
                    for prediction in predictions:
                        context.register_source("result[]", prediction)
                        output = await context.render_variable(self.config.output, ignore_files=True)
                        rendered_outputs.append(output)
                    yield rendered_outputs
                else:
                    yield predictions

        if stream:
            async def _stream_output_generator():
                async for predictions in _predict():
                    if not is_output_array_mode:
                        for prediction in predictions:
                            context.register_source("result", prediction)
                            yield (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
                    else:
                        for prediction in predictions:
                            yield prediction

            return _stream_output_generator()
        else:
            async for predictions in _predict():
                results.extend(predictions)

            if not is_output_array_mode:
                result = results[0] if is_single_input else results
                context.register_source("result", result)

                return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
            else:
                return results

@register_model_task_service(ModelTaskType.TEXT_CLASSIFICATION)
class TextClassificationTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.device: Optional[torch.device] = None

    async def _serve(self) -> None:
        try:
            self.model = self._load_pretrained_model()
            self.tokenizer = self._load_pretrained_tokenizer()
            self.device = self._get_model_device(self.model)
            logging.info(f"Model and tokenizer loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await TextClassificationTaskAction(action, self.model, self.tokenizer, self.device).run(context, self.config.labels)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        return AutoModelForSequenceClassification

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        return AutoTokenizer
