from __future__ import annotations

from typing import Optional, Dict, Any, Union, List
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
            key = await context.render_variable(self.config.key)

            return await self._get(key)

        if method == KeyValueStoreActionMethod.SET:
            key   = await context.render_variable(self.config.key)
            value = await context.render_variable(self.config.value)
            ttl   = await context.render_variable(self.config.ttl) if self.config.ttl is not None else None

            return await self._set(key, value, ttl)

        if method == KeyValueStoreActionMethod.DELETE:
            key = await context.render_variable(self.config.key)

            return await self._delete(key)

        if method == KeyValueStoreActionMethod.EXISTS:
            key = await context.render_variable(self.config.key)

            return await self._exists(key)

        raise ValueError(f"Unsupported key-value store action method: {method}")

    @abstractmethod
    async def _get(self, key: Union[str, List[str]]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _set(self, key: str, value: Any, ttl: Optional[int]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(self, key: Union[str, List[str]]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _exists(self, key: Union[str, List[str]]) -> Dict[str, Any]:
        pass
