from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import AutoModel, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer
from transformers.modeling_outputs import BaseModelOutput
from torch import Tensor
import torch, asyncio

class TextEmbeddingTaskAction:
    def __init__(self, config: TextEmbeddingModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer, device: torch.device):
        self.config: TextEmbeddingModelActionConfig = config
        self.model: PreTrainedModel = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext) -> Any:
        text: Union[str, List[str]] = await context.render_variable(self.config.text)

        max_input_length = await context.render_variable(self.config.params.max_input_length)
        pooling          = await context.render_variable(self.config.params.pooling)
        normalize        = await context.render_variable(self.config.params.normalize)
        batch_size       = await context.render_variable(self.config.params.batch_size)
        stream           = await context.render_variable(self.config.stream)

        is_single_input: bool = bool(not isinstance(text, list))
        is_output_array_mode: bool = context.contains_variable_reference("result[]", self.config.output)
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        async def _embed():
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                inputs: Dict[str, Tensor] = self.tokenizer(batch_texts, return_tensors="pt", max_length=max_input_length, padding=True, truncation=True)
                inputs = { k: v.to(self.device) for k, v in inputs.items() }

                with torch.inference_mode():
                    outputs: BaseModelOutput = self.model(**inputs)
                    last_hidden_state = outputs.last_hidden_state # (batch_size, seq_len, hidden_size)

                attention_mask = inputs.get("attention_mask", None)
                embeddings = self._pool_hidden_state(last_hidden_state, attention_mask, pooling)

                if normalize:
                    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1, eps=1e-12)

                embeddings = embeddings.cpu().tolist()

                if self.config.output and is_output_array_mode:
                    rendered_outputs = []
                    for embedding in embeddings:
                        context.register_source("result[]", embedding)
                        output = await context.render_variable(self.config.output, ignore_files=True)
                        rendered_outputs.append(output)
                    yield rendered_outputs
                else:
                    yield embeddings

        if stream:
            async def _stream_output_generator():
                async for embeddings in _embed():
                    if not is_output_array_mode:
                        for embedding in embeddings:
                            context.register_source("result", embedding)
                            yield (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
                    else:
                        for embedding in embeddings:
                            yield embedding

            return _stream_output_generator()
        else:
            async for embeddings in _embed():
                results.extend(embeddings)

            if not is_output_array_mode:
                result = results[0] if is_single_input else results
                context.register_source("result", result)

                return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
            else:
                return results

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
        return await TextEmbeddingTaskAction(action, self.model, self.tokenizer, self.device).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        return AutoModel

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        return AutoTokenizer
