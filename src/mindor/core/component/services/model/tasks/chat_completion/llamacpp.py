from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.llamacpp import LlamaCppChatCompletionModelComponentConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
from ..text_generation.llamacpp import LlamaCppTextGenerationTaskAction
from .huggingface import HuggingfaceToolBuilder
import asyncio

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppChatCompletionTaskAction(LlamaCppTextGenerationTaskAction):
    config: ChatCompletionModelActionConfig

    def __init__(
        self,
        config: ChatCompletionModelActionConfig,
        model: Llama,
        tools: Optional[List[ModelTool]] = None,
    ):
        super().__init__(config, model)

        self.tools: Optional[List[ModelTool]] = tools

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        if not isinstance(messages, list):
            messages = [ messages ]

        tools = HuggingfaceToolBuilder(self.tools or []).build(tools) or None

        conversation = self._resolve_chat_formatter()(
            messages=messages,
            **({ "tools": tools, "tool_choice": "auto" } if tools else {})
        )

        return conversation.prompt

    async def _process_output(self, result: Any) -> Any:
        return result

    def _process_stream(self, chunks: AsyncIterator[Any]) -> AsyncIterator[Any]:
        return chunks

    def _resolve_chat_formatter(self):
        from llama_cpp import llama_chat_format

        template  = self.model.metadata.get("tokenizer.chat_template")
        eos_token = self.model.detokenize([self.model.token_eos()]).decode("utf-8", errors="ignore")
        bos_token = self.model.detokenize([self.model.token_bos()]).decode("utf-8", errors="ignore")

        if not template:
            raise ValueError("Chat template not found in model metadata; cannot format chat messages.")

        return llama_chat_format.Jinja2ChatFormatter(
            template=template,
            eos_token=eos_token,
            bos_token=bos_token,
        )

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.LLAMACPP)
class LlamaCppChatCompletionTaskService(LlamaCppModelTaskService):
    config: LlamaCppChatCompletionModelComponentConfig

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await LlamaCppChatCompletionTaskAction(action, self.model, self.config.tools).run(context, loop)
