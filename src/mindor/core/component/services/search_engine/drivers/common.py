from __future__ import annotations

from typing import Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineActionMethod
from ..base import ComponentActionContext
import asyncio

class SearchEngineAction:
    def __init__(self, config: SearchEngineActionConfig):
        self.config: SearchEngineActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop, database: Any) -> Any:
        result = await self._dispatch(self.config.method, database, context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _dispatch(self, method: SearchEngineActionMethod, database: Any, context: ComponentActionContext) -> Any:
        if method == SearchEngineActionMethod.INDEX:
            return await self._index(database, context)

        if method == SearchEngineActionMethod.SEARCH:
            return await self._search(database, context)

        if method == SearchEngineActionMethod.DELETE:
            return await self._delete(database, context)

        raise ValueError(f"Unsupported search engine action method: {method}")

    @abstractmethod
    async def _index(self, database: Any, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _search(self, database: Any, context: ComponentActionContext) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _delete(self, database: Any, context: ComponentActionContext) -> Dict[str, Any]:
        pass
