from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import AutoModel, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer
from transformers.modeling_outputs import BaseModelOutput
from torch import Tensor
import torch

class TextEmbeddingTaskAction:
    def __init__(self, config: TextEmbeddingModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer):
        self.config: TextEmbeddingModelActionConfig = config
        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer

    async def run(self, context: ComponentActionContext) -> Any:
        text = await context.render_variable(self.config.text)

        # Model parameters
        max_input_length = await context.render_variable(self.config.params.max_input_length)
        pooling          = await context.render_variable(self.config.params.pooling)
        normalize        = await context.render_variable(self.config.params.normalize)

        # Tokenizing
        inputs = self.tokenizer(text, return_tensors="pt", max_length=max_input_length, padding=True, truncation=True).to(self.model.device)
        attention_mask: Tensor = inputs.get("attention_mask", None)

        # Forward pass through the model
        with torch.no_grad():
            outputs: BaseModelOutput = self.model(**inputs)
            last_hidden_state = outputs.last_hidden_state  # (batch_size, seq_len, hidden_size)

        # Apply pooling strategy (mean, cls, max)
        embedding = self._pool_hidden_state(last_hidden_state, attention_mask, pooling)

        if normalize:
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        result = embedding.squeeze().tolist()
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    def _pool_hidden_state(self, last_hidden_state: Tensor, attention_mask: Optional[Tensor], pooling: str) -> Tensor:
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

@register_model_task_service(ModelTaskType.TEXT_EMBEDDING)
class TextEmbeddingTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None

    async def _serve(self) -> None:
        try:
            self.model = AutoModel.from_pretrained(self.config.model).to(torch.device(self.config.device))
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model, use_fast=self.config.fast_tokenizer)
            logging.info(f"Model and tokenizer loaded successfully on device '{self.config.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.tokenizer = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await TextEmbeddingTaskAction(action, self.model, self.tokenizer).run(context)
