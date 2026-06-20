from __future__ import annotations

from typing import Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import KeyValueStoreActionConfig, KeyValueStoreActionMethod
from ..base import ComponentActionContext

class KeyValueStoreAction:
    def __init__(self, config: KeyValueStoreActionConfig):
        self.config: KeyValueStoreActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        result = await self._dispatch(self.config.method, context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _dispatch(self, method: KeyValueStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == KeyValueStoreActionMethod.GET:
            return await self._get(context)

        if method == KeyValueStoreActionMethod.SET:
            return await self._set(context)

        if method == KeyValueStoreActionMethod.DELETE:
            return await self._delete(context)

        if method == KeyValueStoreActionMethod.EXISTS:
            return await self._exists(context)

        raise ValueError(f"Unsupported key-value store action method: {method}")

    @abstractmethod
    async def _get(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _set(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _exists(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass
