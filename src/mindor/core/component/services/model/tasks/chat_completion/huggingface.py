from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import HuggingfaceLanguageModelTaskService, ComponentActionContext
from ..text_generation import HuggingfaceTextGenerationTaskAction
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    import torch

class HuggingfaceChatCompletionTaskAction(HuggingfaceTextGenerationTaskAction):
    def __init__(self, config: ChatCompletionModelActionConfig, model: PreTrainedModel, tokenizer: PreTrainedTokenizer, device: torch.device):
        super().__init__(config, model, tokenizer, device)

        self.config: ChatCompletionModelActionConfig = config # For type only

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        messages = await context.render_variable(self.config.messages)

        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.HUGGINGFACE)
class HuggingfaceChatCompletionTaskService(HuggingfaceLanguageModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await HuggingfaceChatCompletionTaskAction(action, self.model, self.tokenizer, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForCausalLM
        return AutoModelForCausalLM

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
