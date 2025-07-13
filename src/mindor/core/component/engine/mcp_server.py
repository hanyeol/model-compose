from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import McpServerComponentConfig
from ..base import ComponentEngine, ComponentType, ActionConfig, register_component
from ..context import ComponentActionContext

@register_component(ComponentType.MCP_SERVER)
class McpServerComponent(ComponentEngine):
    def __init__(self, id: str, config: McpServerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return {}
