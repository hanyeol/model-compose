from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.vllm import VllmChatCompletionModelComponentConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from ..text_generation.vllm import VllmTextGenerationTaskAction
from .huggingface import HuggingfaceToolBuilder
import asyncio

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

class VllmChatCompletionTaskAction(VllmTextGenerationTaskAction):
    config: ChatCompletionModelActionConfig

    def __init__(
        self,
        config: ChatCompletionModelActionConfig,
        engine: AsyncLLMEngine,
        tokenizer: PreTrainedTokenizerBase,
        tools: Optional[List[ModelTool]] = None,
    ):
        super().__init__(config, engine)

        self.tokenizer: PreTrainedTokenizerBase = tokenizer
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

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.VLLM)
class VllmChatCompletionTaskService(VllmModelTaskService):
    config: VllmChatCompletionModelComponentConfig

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await VllmChatCompletionTaskAction(action, self.engine, self.tokenizer, self.config.tools).run(context, loop)
