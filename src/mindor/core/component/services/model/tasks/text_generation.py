from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextGenerationModelActionConfig
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer, GenerationMixin
import torch

class TextGenerationTaskAction:
    def __init__(self, config: TextGenerationModelActionConfig, model: Union[PreTrainedModel, GenerationMixin], tokenizer: PreTrainedTokenizer):
        self.config: TextGenerationModelActionConfig = config
        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.tokenizer: PreTrainedTokenizer = tokenizer

    async def run(self, context: ComponentActionContext) -> Any:
        prompt: Union[str, List[str]] = await context.render_variable(self.config.prompt)

        # Model parameters
        max_output_length    = await context.render_variable(self.config.params.max_output_length)
        num_return_sequences = await context.render_variable(self.config.params.num_return_sequences)
        temperature          = await context.render_variable(self.config.params.temperature)
        top_k                = await context.render_variable(self.config.params.top_k)
        top_p                = await context.render_variable(self.config.params.top_p)

        # Tokenizing
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        # Text generation
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_output_length,
                num_return_sequences=num_return_sequences,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                do_sample=True
            )

        # Decoding output
        outputs = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
        
        result = outputs if isinstance(prompt, list) else outputs[0] 
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

@register_model_task_service(ModelTaskType.TEXT_GENERATION)
class TextGenerationTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Union[PreTrainedModel, GenerationMixin]] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None

    async def _serve(self) -> None:
        try:
            self.model = AutoModelForCausalLM.from_pretrained(self.config.model).to(torch.device(self.config.device))
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model, use_fast=self.config.fast_tokenizer)
            logging.info(f"Model and tokenizer loaded successfully on device '{self.config.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.tokenizer = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await TextGenerationTaskAction(action, self.model, self.tokenizer).run(context)
