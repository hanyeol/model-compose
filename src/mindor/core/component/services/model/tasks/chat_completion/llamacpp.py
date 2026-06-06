from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, ChatCompletionModelActionConfig
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppChatCompletionTaskAction:
    def __init__(
        self,
        config: ChatCompletionModelActionConfig,
        model: Llama,
    ):
        self.config: ChatCompletionModelActionConfig = config
        self.model: Llama = model

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        messages      = await context.render_variable(self.config.messages)
        tools         = await context.render_variable(self.config.tools)
        streaming     = await context.render_variable(self.config.streaming)
        gen_params    = await self._resolve_generation_params(context)

        if not isinstance(messages, list):
            messages = [messages]

        normalized_messages = [self._normalize_message(m) for m in messages]

        call_params: Dict[str, Any] = {
            "messages": normalized_messages,
            "stream": bool(streaming),
            **gen_params,
        }

        if tools:
            call_params["tools"] = [self._build_tool_definition(t) for t in tools]
            call_params["tool_choice"] = "auto"

        if streaming:
            response = self.model.create_chat_completion(**call_params)

            async def _stream_output_generator():
                for chunk in response:
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield await self._render_output_chunk(context, token)

            return _stream_output_generator()
        else:
            response = self.model.create_chat_completion(**call_params)
            choice = response["choices"][0]
            message = choice["message"]

            tool_calls = message.get("tool_calls")
            if tool_calls:
                result = {
                    "role": message.get("role", "assistant"),
                    "content": message.get("content"),
                    "tool_calls": tool_calls,
                }
            else:
                result = message.get("content", "")

            return await self._render_output(context, result)

    def _normalize_message(self, message: Any) -> Dict[str, Any]:
        if isinstance(message, dict):
            return message
        if hasattr(message, "model_dump"):
            return {k: v for k, v in message.model_dump().items() if v is not None}
        return dict(message)

    def _build_tool_definition(self, tool: Any) -> Dict[str, Any]:
        if isinstance(tool, dict):
            func = tool
        elif hasattr(tool, "model_dump"):
            func = {k: v for k, v in tool.model_dump().items() if v is not None}
        else:
            func = dict(tool)

        return {"type": "function", "function": func}

    async def _render_output_chunk(self, context: ComponentActionContext, chunk: str) -> Any:
        context.register_source("result[]", chunk)
        return (await context.render_variable(self.config.output)) if self.config.output else chunk

    async def _render_output(self, context: ComponentActionContext, result: Any) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_output_length = await context.render_variable(self.config.params.max_output_length)
        do_sample         = await context.render_variable(self.config.params.do_sample)
        temperature       = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k             = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p             = await context.render_variable(self.config.params.top_p) if do_sample else None
        stop_sequences    = await context.render_variable(self.config.stop_sequences)

        params: Dict[str, Any] = {
            "max_tokens": max_output_length,
        }

        if do_sample:
            if temperature is not None:
                params["temperature"] = temperature
            if top_k is not None:
                params["top_k"] = top_k
            if top_p is not None:
                params["top_p"] = top_p
        else:
            params["temperature"] = 0.0

        if stop_sequences:
            params["stop"] = stop_sequences if isinstance(stop_sequences, list) else [stop_sequences]

        return params


@register_model_task_service(ModelTaskType.CHAT_COMPLETION, ModelDriver.LLAMACPP)
class LlamaCppChatCompletionTaskService(LlamaCppModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await LlamaCppChatCompletionTaskAction(action, self.model).run(context, loop)
