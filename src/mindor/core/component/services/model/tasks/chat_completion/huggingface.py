from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.huggingface import HuggingfaceChatCompletionModelComponentConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from ..text_generation.huggingface import HuggingfaceTextGenerationTaskAction
from .common import ToolBuilder
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    import torch

class HuggingfaceToolBuilder(ToolBuilder):
    def _build_tool(self, tool: ModelTool) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": tool.model_dump(exclude_none=True),
        }

class HuggingfaceChatCompletionTaskAction(HuggingfaceTextGenerationTaskAction):
    config: ChatCompletionModelActionConfig

    def __init__(
        self,
        config: ChatCompletionModelActionConfig,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizer,
        device: torch.device,
        tools: Optional[List[ModelTool]] = None,
    ):
        super().__init__(config, model, tokenizer, device)

        self.tools: Optional[List[ModelTool]] = tools

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        tools = HuggingfaceToolBuilder(self.tools or []).build(tools) or None

        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            **({ "tools": tools } if tools else {})
        )

    async def _process_output(self, result: Any) -> Any:
        return result

    def _process_stream(self, chunks: AsyncIterator[Any]) -> AsyncIterator[Any]:
        return chunks

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.HUGGINGFACE)
class HuggingfaceChatCompletionTaskService(HuggingfaceLanguageModelTaskService):
    config: HuggingfaceChatCompletionModelComponentConfig

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceChatCompletionTaskAction(action, self.model, self.tokenizer, self.device, self.config.tools).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForCausalLM
        return AutoModelForCausalLM

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
