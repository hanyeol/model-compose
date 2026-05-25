from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import SearchEngineComponentConfig, SearchEngineDriver
from mindor.dsl.schema.action import SearchEngineActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class SearchEngineService(AsyncService):
    def __init__(self, id: str, config: SearchEngineComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: SearchEngineComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_search_engine_service(driver: SearchEngineDriver):
    def decorator(cls: Type[SearchEngineService]) -> Type[SearchEngineService]:
        SearchEngineServiceRegistry[driver] = cls
        return cls
    return decorator

SearchEngineServiceRegistry: Dict[SearchEngineDriver, Type[SearchEngineService]] = {}
