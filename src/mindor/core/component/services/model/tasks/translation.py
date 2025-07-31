from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TranslationModelActionConfig
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer, GenerationMixin
from torch import Tensor
import torch

class TranslationTaskAction:
    def __init__(self, config: TranslationModelActionConfig, model: Union[PreTrainedModel, GenerationMixin], tokenizer: PreTrainedTokenizer, device: torch.device):
        self.config: TranslationModelActionConfig = config
        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.tokenizer: PreTrainedTokenizer = tokenizer
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext) -> Any:
        text: Union[str, List[str]] = await context.render_variable(self.config.text)

        max_input_length  = await context.render_variable(self.config.params.max_input_length)
        max_output_length = await context.render_variable(self.config.params.max_output_length)
        min_output_length = await context.render_variable(self.config.params.min_output_length)
        num_beams         = await context.render_variable(self.config.params.num_beams)
        length_penalty    = await context.render_variable(self.config.params.length_penalty)
        batch_size        = await context.render_variable(self.config.params.batch_size)

        texts: List[str] = [ text ] if isinstance(text, str) else text
        results = []

        for index in range(0, len(texts), batch_size):
            batch_texts = texts[index:index + batch_size]
            inputs: Dict[str, Tensor] = self.tokenizer(batch_texts, return_tensors="pt", max_length=max_input_length, padding=True, truncation=True)
            inputs = { k: v.to(self.device) for k, v in inputs.items() }
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=max_output_length,
                    min_length=min_output_length,
                    num_beams=num_beams,
                    length_penalty=length_penalty,
                    do_sample=False,
                    pad_token_id=getattr(self.tokenizer, "pad_token_id", None),
                    eos_token_id=getattr(self.tokenizer, "eos_token_id", None)
                )

            outputs = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
            results.extend(outputs)
        
        result = results if len(results) > 1 else results[0]
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

@register_model_task_service(ModelTaskType.TRANSLATION)
class TranslationTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Union[PreTrainedModel, GenerationMixin]] = None
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

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await TranslationTaskAction(action, self.model, self.tokenizer, self.device).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        return AutoModelForSeq2SeqLM

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        return AutoTokenizer
