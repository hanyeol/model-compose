from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import McpServerComponentConfig
from mindor.dsl.schema.action import ActionConfig, McpServerActionConfig
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext

class McpServerAction:
    def __init__(self, config: McpServerActionConfig):
        self.config: McpServerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        pass

@register_component(ComponentType.MCP_SERVER)
class McpServerComponent(ComponentService):
    def __init__(self, id: str, config: McpServerComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await McpServerAction(action).run(context)

