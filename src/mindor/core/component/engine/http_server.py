from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import HttpServerComponentConfig
from ..base import ComponentEngine, ComponentType, ActionConfig, register_component
from ..context import ComponentActionContext

@register_component(ComponentType.HTTP_SERVER)
class HttpServerComponent(ComponentEngine):
    def __init__(self, id: str, config: HttpServerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return {}
