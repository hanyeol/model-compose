from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from ..base import ComponentActionContext
import asyncio

class VectorStoreAction:
    def __init__(self, config: VectorStoreActionConfig, client: Any):
        self.config: VectorStoreActionConfig = config
        self.client: Any = client

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _dispatch(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Any:
        if method == VectorStoreActionMethod.INSERT:
            return await self._insert(context)

        if method == VectorStoreActionMethod.UPDATE:
            return await self._update(context)

        if method == VectorStoreActionMethod.SEARCH:
            return await self._search(context)

        if method == VectorStoreActionMethod.DELETE:
            return await self._delete(context)

        raise ValueError(f"Unsupported vector action method: {method}")

    @abstractmethod
    async def _insert(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _update(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _search(self, context: ComponentActionContext) -> Any:
        pass

    @abstractmethod
    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass
