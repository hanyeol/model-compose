from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import HttpServerComponentConfig
from .base import ComponentEngine, ComponentType, ComponentEngineMap, ActionConfig
from .context import ComponentContext

class HttpServerComponent(ComponentEngine):
    def __init__(self, id: str, config: HttpServerComponentConfig, env: Dict[str, str], daemon: bool):
        super().__init__(id, config, env, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentContext) -> Any:
        return {}

ComponentEngineMap[ComponentType.HTTP_SERVER] = HttpServerComponent
