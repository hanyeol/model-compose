from __future__ import annotations

from typing import Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import GraphStoreActionConfig, GraphStoreActionMethod
from ..base import ComponentActionContext
import asyncio

class GraphStoreAction:
    def __init__(self, config: GraphStoreActionConfig, database: Any):
        self.config: GraphStoreActionConfig = config
        self.database: Any = database

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _dispatch(self, method: GraphStoreActionMethod, context: ComponentActionContext) -> Any:
        if method == GraphStoreActionMethod.QUERY:
            return await self._query(context)

        if method == GraphStoreActionMethod.INSERT:
            return await self._insert(context)

        if method == GraphStoreActionMethod.UPDATE:
            return await self._update(context)

        if method == GraphStoreActionMethod.DELETE:
            return await self._delete(context)

        if method == GraphStoreActionMethod.TRAVERSE:
            return await self._traverse(context)

        raise ValueError(f"Unsupported graph action method: {method}")

    @abstractmethod
    async def _query(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _insert(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _update(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _traverse(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        pass
