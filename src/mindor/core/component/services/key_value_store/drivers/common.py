from __future__ import annotations

from typing import Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import KeyValueStoreActionConfig, KeyValueStoreActionMethod
from mindor.core.foundation.cancellation import CancellationToken
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class KeyValueStoreAction(ComponentAction):
    def __init__(self, config: KeyValueStoreActionConfig):
        self.config: KeyValueStoreActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, params, context.cancellation_token)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _dispatch(
        self,
        method: KeyValueStoreActionMethod,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if method == KeyValueStoreActionMethod.GET:
            return await self._get(params, cancellation_token)

        if method == KeyValueStoreActionMethod.SET:
            return await self._set(params, cancellation_token)

        if method == KeyValueStoreActionMethod.DELETE:
            return await self._delete(params, cancellation_token)

        if method == KeyValueStoreActionMethod.EXISTS:
            return await self._exists(params, cancellation_token)

        raise ValueError(f"Unsupported key-value store action method: {method}")

    async def _resolve_params(self, method: KeyValueStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == KeyValueStoreActionMethod.GET:
            key = await context.render_variable(self.config.key)

            return {
                "key": key,
            }

        if method == KeyValueStoreActionMethod.SET:
            key   = await context.render_variable(self.config.key)
            value = await context.render_variable(self.config.value)
            ttl   = await context.render_variable(self.config.ttl) if self.config.ttl is not None else None

            return {
                "key":   key,
                "value": value,
                "ttl":   ttl,
            }

        if method == KeyValueStoreActionMethod.DELETE:
            key = await context.render_variable(self.config.key)

            return {
                "key": key,
            }

        if method == KeyValueStoreActionMethod.EXISTS:
            key = await context.render_variable(self.config.key)

            return {
                "key": key,
            }

        raise ValueError(f"Unsupported key-value store action method: {method}")

    @abstractmethod
    async def _get(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _set(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _exists(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        pass
