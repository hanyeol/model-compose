from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import GraphStoreComponentConfig, GraphStoreDriver
from mindor.dsl.schema.action import GraphStoreActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class GraphStoreService(AsyncService):
    def __init__(self, id: str, config: GraphStoreComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: GraphStoreComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_graph_store_service(driver: GraphStoreDriver):
    def decorator(cls: Type[GraphStoreService]) -> Type[GraphStoreService]:
        GraphStoreServiceRegistry[driver] = cls
        return cls
    return decorator

GraphStoreServiceRegistry: Dict[GraphStoreDriver, Type[GraphStoreService]] = {}
