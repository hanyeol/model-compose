from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from ..text_generation.vllm import VllmTextGenerationTaskAction
import asyncio

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

class VllmChatCompletionTaskAction(VllmTextGenerationTaskAction):
    def __init__(
        self,
        config: ChatCompletionModelActionConfig,
        engine: AsyncLLMEngine,
        tokenizer: PreTrainedTokenizerBase,
    ):
        super().__init__(config, engine)

        self.config: ChatCompletionModelActionConfig = config  # For type only
        self.tokenizer: PreTrainedTokenizerBase = tokenizer

    async def _prepare_input(self, context: ComponentActionContext) -> str:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        if not isinstance(messages, list):
            messages = [ messages ]

        normalized_messages = [ self._normalize_message(m) for m in messages ]
        normalized_tools = [ self._build_tool_definition(t) for t in tools ] if tools else None

        kwargs: Dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if normalized_tools:
            kwargs["tools"] = normalized_tools

        return self.tokenizer.apply_chat_template(normalized_messages, **kwargs)

    def _build_output(self, choice: Dict[str, Any], streaming: bool) -> Any:
        text = choice.get("text", "")
        if streaming:
            return { "content": text } if text else None
        return { "role": "assistant", "content": text }

    def _normalize_message(self, message: Any) -> Dict[str, Any]:
        if isinstance(message, dict):
            return message
        if hasattr(message, "model_dump"):
            return { k: v for k, v in message.model_dump().items() if v is not None }
        return dict(message)

    def _build_tool_definition(self, tool: Any) -> Dict[str, Any]:
        if isinstance(tool, dict):
            func = tool
        elif hasattr(tool, "model_dump"):
            func = { k: v for k, v in tool.model_dump().items() if v is not None }
        else:
            func = dict(tool)

        return { "type": "function", "function": func }


@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.VLLM)
class VllmChatCompletionTaskService(VllmModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await VllmChatCompletionTaskAction(action, self.engine, self.tokenizer).run(context, loop)
