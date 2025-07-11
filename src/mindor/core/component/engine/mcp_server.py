from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import McpServerComponentConfig
from .base import ComponentEngine, ComponentType, ComponentEngineMap, ActionConfig
from .context import ComponentActionContext

class McpServerComponent(ComponentEngine):
    def __init__(self, id: str, config: McpServerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return {}

ComponentEngineMap[ComponentType.MCP_SERVER] = McpServerComponent
