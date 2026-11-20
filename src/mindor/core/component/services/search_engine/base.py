from typing import Type, Literal, Optional, Dict, List, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import SearchEngineComponentConfig, SearchEngineDriverType
from mindor.dsl.schema.action import SearchEngineActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class SearchEngineDriver(ComponentDriver):
    config: SearchEngineComponentConfig

    async def run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_search_engine_driver(driver: SearchEngineDriverType):
    def decorator(cls: Type[SearchEngineDriver]) -> Type[SearchEngineDriver]:
        SearchEngineDriverRegistry[driver] = cls
        return cls
    return decorator

SearchEngineDriverRegistry: Dict[SearchEngineDriverType, Type[SearchEngineDriver]] = {}
