from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.huggingface import HuggingfaceChatCompletionModelComponentConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import ToolCallParserConfig, ReasoningParserConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.language import HuggingfaceLanguageModelTaskService
from ..text_generation.huggingface import HuggingfaceTextGenerationTaskAction
from .common import ChatToolBuilder, ChatChoicesBuilder, ToolCallParser, ReasoningParser

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    import torch

class HuggingfaceToolBuilder(ChatToolBuilder):
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
        chat_template: Optional[str] = None,
        tool_call_parser: Optional[ToolCallParserConfig] = None,
        reasoning_parser: Optional[ReasoningParserConfig] = None,
    ):
        super().__init__(config, model, tokenizer, device)

        self.tools: Optional[List[ModelTool]] = tools
        self.chat_template: Optional[str] = chat_template
        self.tool_call_parser: Optional[ToolCallParser] = ToolCallParser(tool_call_parser) if tool_call_parser else None
        self.reasoning_parser: Optional[ReasoningParser] = ReasoningParser(reasoning_parser) if reasoning_parser else None

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        tools = HuggingfaceToolBuilder(self.tools or []).build(tools) or None

        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            **({ "tools": tools } if tools else {}),
            **({ "chat_template": self.chat_template } if self.chat_template else {}),
        )

    def _process_sequences(self, sequences: Union[List[str], List[AsyncIterator[str]]], streaming: bool) -> Any:
        builder = ChatChoicesBuilder(self.tool_call_parser, self.reasoning_parser)

        if streaming:
            return builder.stream(sequences)

        return builder.build(sequences)

@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.HUGGINGFACE)
class HuggingfaceChatCompletionTaskService(HuggingfaceLanguageModelTaskService):
    config: HuggingfaceChatCompletionModelComponentConfig

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext
    ) -> Any:
        return await HuggingfaceChatCompletionTaskAction(
            action,
            self.model,
            self.tokenizer,
            self.device,
            self.config.tools,
            self.config.chat_template,
            self.config.tool_call_parser,
            self.config.reasoning_parser,
        ).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForCausalLM
        return AutoModelForCausalLM

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        from transformers import AutoTokenizer
        return AutoTokenizer
