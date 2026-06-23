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

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        messages = await context.render_variable(self.config.messages)
        tools    = await context.render_variable(self.config.tools)

        tools = [ self._build_function_tool(tool) for tool in tools ] if tools else None

        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            **({ "tools": tools } if tools else {})
        )

    def _build_function_tool(self, function: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": { k: v for k, v in function.items() if v is not None }
        }


@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.VLLM)
class VllmChatCompletionTaskService(VllmModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await VllmChatCompletionTaskAction(action, self.engine, self.tokenizer).run(context, loop)
