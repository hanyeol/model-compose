from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.vllm import VllmChatCompletionModelComponentConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import ToolCallParserConfig, ReasoningParserConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from ..text_generation.vllm import VllmTextGenerationTaskAction
from .common import ChatChoicesBuilder, ToolCallParser, ReasoningParser
from .huggingface import HuggingfaceToolBuilder

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
        chat_template: Optional[str] = None,
        tool_call_parser: Optional[ToolCallParserConfig] = None,
        reasoning_parser: Optional[ReasoningParserConfig] = None,
    ):
        super().__init__(config, engine)

        self.tokenizer: PreTrainedTokenizerBase = tokenizer
        self.tools: Optional[List[ModelTool]] = tools
        self.chat_template: Optional[str] = chat_template
        self.tool_call_parser: Optional[ToolCallParser] = ToolCallParser(tool_call_parser) if tool_call_parser else None
        self.reasoning_parser: Optional[ReasoningParser] = ReasoningParser(reasoning_parser) if reasoning_parser else None

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str], AsyncIterator[str]]:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        tools = HuggingfaceToolBuilder(self.tools or []).build(tools) or None

        if isinstance(messages, (StreamIterator, AsyncIterator)):
            async def _iterate_prompts(batch_messages):
                async for messages in batch_messages:
                    yield self._build_chat_prompt(messages, tools)

            return _iterate_prompts(messages)

        if isinstance(messages, list) and len(messages) > 0 and isinstance(messages[0], list):
            def _list_prompts(batch_messages):
                return [ self._build_chat_prompt(messages, tools) for messages in batch_messages ]

            return _list_prompts(messages)

        return self._build_chat_prompt(messages, tools)

    def _build_chat_prompt(
        self,
        messages: Union[Dict[str, Any], List[Dict[str, Any]]],
        tools: Optional[List[Dict[str, Any]]]
    ) -> str:
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            **({ "tools": tools } if tools else {}),
            **({ "chat_template": self.chat_template } if self.chat_template else {}),
        )

    def _process_sequences(
        self,
        sequences: Union[List[str], List[AsyncIterator[str]]],
        streaming: bool
    ) -> Any:
        builder = ChatChoicesBuilder(self.tool_call_parser, self.reasoning_parser)

        if streaming:
            return builder.stream(sequences)

        return builder.build(sequences)

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.VLLM)
class VllmChatCompletionTaskService(VllmModelTaskService):
    config: VllmChatCompletionModelComponentConfig

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext
    ) -> Any:
        return await VllmChatCompletionTaskAction(
            action,
            self.engine,
            self.tokenizer,
            self.config.tools,
            self.config.chat_template,
            self.config.tool_call_parser,
            self.config.reasoning_parser,
        ).run(context)
