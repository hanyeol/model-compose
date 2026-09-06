import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.common.model.tool import ModelTool

def build_choices_envelope(sequences: List[str]) -> Dict[str, Any]:
    """Wrap n completed sequences into an OpenAI-compatible choices envelope."""
    return {
        "choices": [
            {
                "index": index,
                "content": [ { "type": "text", "text": text } ],
                "finish_reason": "stop",
            }
            for index, text in enumerate(sequences)
        ],
    }

async def stream_choices_envelope(sequences: List[AsyncIterator[str]]) -> AsyncIterator[Dict[str, Any]]:
    """Merge n per-sequence text streams into a single choices-envelope delta stream.

    Each backend text chunk becomes
    ``{ choices: [ { index, delta: {type,text}, finish_reason: None } ] }``.
    When a sequence finishes, a terminator with ``finish_reason: "stop"`` and no
    delta is emitted for that index so consumers can detect per-sequence
    completion without a sentinel.
    """
    n = len(sequences)
    queue: asyncio.Queue = asyncio.Queue()
    end = object()

    async def _pump(index: int, source: AsyncIterator[str]) -> None:
        try:
            async for chunk in source:
                if not chunk:
                    continue
                await queue.put({
                    "choices": [ {
                        "index": index,
                        "delta": { "type": "text", "text": chunk },
                        "finish_reason": None,
                    } ],
                })
            await queue.put({
                "choices": [ {
                    "index": index,
                    "delta": {},
                    "finish_reason": "stop",
                } ],
            })
        finally:
            await queue.put(end)

    tasks = [ asyncio.create_task(_pump(index, source)) for index, source in enumerate(sequences) ]
    remaining = n

    try:
        while remaining > 0:
            chunk = await queue.get()
            if chunk is end:
                remaining -= 1
                continue
            yield chunk
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()

class ToolBuilder(ABC):
    def __init__(self, tools: List[ModelTool]):
        self.tools: List[ModelTool] = tools

    def build(self, tools: Optional[Union[List[str], List[ModelTool]]]) -> List[Dict[str, Any]]:
        if tools is None or all(isinstance(tool, str) for tool in tools):
            tools = self._select_tools(tools)
        return [ self._build_tool(tool) for tool in tools ]

    def _select_tools(self, names: Optional[List[str]]) -> List[ModelTool]:
        tools: List[ModelTool] = []

        if names is not None:
            for name in names:
                tool = next((tool for tool in self.tools if tool.name == name), None)
                if not tool:
                    raise LookupError(f"Tool '{name}' is not defined in the component's tool catalog.")
                tools.append(tool)
        else:
            tools.extend(self.tools)

        return tools

    @abstractmethod
    def _build_tool(self, tool: ModelTool) -> Dict[str, Any]:
        pass
