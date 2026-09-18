from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import GraphStoreComponentConfig, GraphStoreDriverType
from mindor.dsl.schema.action import GraphStoreActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class GraphStoreDriver(ComponentDriver):
    def __init__(self, id: str, config: GraphStoreComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: GraphStoreComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_graph_store_driver(driver: GraphStoreDriverType):
    def decorator(cls: Type[GraphStoreDriver]) -> Type[GraphStoreDriver]:
        GraphStoreDriverRegistry[driver] = cls
        return cls
    return decorator

GraphStoreDriverRegistry: Dict[GraphStoreDriverType, Type[GraphStoreDriver]] = {}
