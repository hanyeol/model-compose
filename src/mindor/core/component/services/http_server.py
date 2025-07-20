from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import HttpServerComponentConfig
from mindor.dsl.schema.action import ActionConfig, HttpServerActionConfig
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext

class HttpServerAction:
    def __init__(self, config: HttpServerActionConfig):
        self.config: HttpServerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        pass

@register_component(ComponentType.HTTP_SERVER)
class HttpServerComponent(ComponentService):
    def __init__(self, id: str, config: HttpServerComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await HttpServerAction(action).run(context)
