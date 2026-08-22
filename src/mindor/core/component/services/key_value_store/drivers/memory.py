from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import MemoryKeyValueStoreComponentConfig
from mindor.dsl.schema.action import KeyValueStoreActionConfig, MemoryKeyValueStoreActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..base import KeyValueStoreService, KeyValueStoreDriver, register_kv_store_service
from ..base import ComponentActionContext
from .common import KeyValueStoreAction
import asyncio, time

class MemoryKeyValueStoreAction(KeyValueStoreAction):
    def __init__(self, config: MemoryKeyValueStoreActionConfig, store: Dict[str, Tuple[Any, Optional[float]]], lock: asyncio.Lock):
        super().__init__(config)

        self.store: Dict[str, Tuple[Any, Optional[float]]] = store
        self.lock: asyncio.Lock = lock

    async def _get(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        async with self.lock:
            results: List[Dict[str, Any]] = []

            for key in keys:
                value = self._get_active_value(key)
                results.append({ "key": key, "value": value })

            return results

    async def _set(
        self,
        keys: List[str],
        values: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        expires_at = (time.monotonic() + params["ttl"]) if params["ttl"] is not None else None

        async with self.lock:
            results: List[Dict[str, Any]] = []

            for key, value in zip(keys, values):
                self.store[key] = (value, expires_at)
                results.append({ "key": key, "success": True })

            return results

    async def _delete(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        async with self.lock:
            results: List[Dict[str, Any]] = []

            for key in keys:
                # `_get_active_value` drops expired items, so a truthy result means
                # the key was live — that's the only case counted as deleted.
                deleted = self._get_active_value(key) is not None
                self.store.pop(key, None)
                results.append({ "key": key, "deleted": deleted })

            return results

    async def _exists(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        async with self.lock:
            results: List[Dict[str, Any]] = []

            for key in keys:
                results.append({ "key": key, "exists": self._get_active_value(key) is not None })

            return results

    def _get_active_value(self, key: str) -> Any:
        item = self.store.get(key)

        if item is None:
            return None

        value, expires_at = item
        if expires_at is not None and time.monotonic() >= expires_at:
            self.store.pop(key, None)
            return None

        return value

@register_kv_store_service(KeyValueStoreDriver.MEMORY)
class MemoryKeyValueStoreService(KeyValueStoreService):
    def __init__(self, id: str, config: MemoryKeyValueStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self.lock: asyncio.Lock = asyncio.Lock()

    async def _start(self) -> None:
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        self.store.clear()

    async def _run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        return await MemoryKeyValueStoreAction(action, self.store, self.lock).run(context)
