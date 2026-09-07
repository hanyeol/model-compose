from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.llamacpp import LlamaCppChatCompletionModelComponentConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import ToolCallParserConfig, ReasoningParserConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
from ..text_generation.llamacpp import LlamaCppTextGenerationTaskAction
from .common import ChatChoicesBuilder, ToolCallParser, ReasoningParser
from .huggingface import HuggingfaceToolBuilder

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppChatCompletionTaskAction(LlamaCppTextGenerationTaskAction):
    config: ChatCompletionModelActionConfig

    def __init__(
        self,
        config: ChatCompletionModelActionConfig,
        model: Llama,
        tools: Optional[List[ModelTool]] = None,
        chat_template: Optional[str] = None,
        tool_call_parser: Optional[ToolCallParserConfig] = None,
        reasoning_parser: Optional[ReasoningParserConfig] = None,
    ):
        super().__init__(config, model)

        self.tools: Optional[List[ModelTool]] = tools
        self.chat_template: Optional[str] = chat_template
        self.tool_call_parser: Optional[ToolCallParser] = ToolCallParser(tool_call_parser) if tool_call_parser else None
        self.reasoning_parser: Optional[ReasoningParser] = ReasoningParser(reasoning_parser) if reasoning_parser else None

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str], AsyncIterator[str]]:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        tools = HuggingfaceToolBuilder(self.tools or []).build(tools) or None

        if isinstance(messages, (StreamIterator, AsyncIterator)):
            formatter = self._resolve_chat_formatter()

            async def _iterate_prompts(batch_messages):
                async for messages in batch_messages:
                    yield self._build_chat_prompt(messages, tools, formatter)

            return _iterate_prompts(messages)

        if isinstance(messages, list) and len(messages) > 0 and isinstance(messages[0], list):
            formatter = self._resolve_chat_formatter()

            def _list_prompts(batch_messages):
                return [ self._build_chat_prompt(messages, tools, formatter) for messages in batch_messages ]

            return _list_prompts(messages)
    
        return self._build_chat_prompt(messages, tools, self._resolve_chat_formatter())

    def _build_chat_prompt(
        self,
        messages: Union[Dict[str, Any], List[Dict[str, Any]]],
        tools: Optional[List[Dict[str, Any]]],
        formatter: Any
    ) -> str:
        if not isinstance(messages, list):
            messages = [ messages ]

        conversation = formatter(
            messages=messages,
            **({ "tools": tools, "tool_choice": "auto" } if tools else {})
        )

        return conversation.prompt

    def _process_sequences(
        self,
        sequences: Union[List[str], List[AsyncIterator[str]]],
        streaming: bool
    ) -> Any:
        builder = ChatChoicesBuilder(self.tool_call_parser, self.reasoning_parser)

        if streaming:
            return builder.stream(sequences)

        return builder.build(sequences)

    def _resolve_chat_formatter(self):
        from llama_cpp import llama_chat_format

        template  = self.chat_template or self.model.metadata.get("tokenizer.chat_template")
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
        context: ComponentActionContext
    ) -> Any:
        return await LlamaCppChatCompletionTaskAction(
            action,
            self.model,
            self.config.tools,
            self.config.chat_template,
            self.config.tool_call_parser,
            self.config.reasoning_parser,
        ).run(context)
