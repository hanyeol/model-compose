from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union, Any
from mindor.dsl.schema.common.model.tool import ModelTool

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
