from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import RedisKeyValueStoreComponentConfig
from mindor.dsl.schema.action import KeyValueStoreActionConfig, RedisKeyValueStoreActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..base import KeyValueStoreService, KeyValueStoreDriver, register_kv_store_service
from ..base import ComponentActionContext
from .common import KeyValueStoreAction
import json

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

class RedisKeyValueStoreAction(KeyValueStoreAction):
    def __init__(self, config: RedisKeyValueStoreActionConfig, client: AsyncRedis):
        super().__init__(config)

        self.client: AsyncRedis = client

    async def _get(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        values = await self.client.mget(keys) if keys else []

        return [ { "key": key, "value": self._decode_value(value) } for key, value in zip(keys, values) ]

    async def _set(
        self,
        keys: List[str],
        values: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        values = [ self._encode_value(value) for value in values ]

        if params["ttl"] is not None:
            async with self.client.pipeline(transaction=False) as p:
                for key, value in zip(keys, values):
                    p.setex(key, params["ttl"], value)
                results = await p.execute()
        else:
            result = await self.client.mset(dict(zip(keys, values)))
            results = [ result ] * len(keys)

        return [ { "key": key, "success": bool(result) } for key, result in zip(keys, results) ]

    async def _delete(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        # `DEL k1 k2 ...` returns only a total count. Use a pipeline so each
        # response entry can report whether that specific key was removed.
        async with self.client.pipeline(transaction=False) as p:
            for key in keys:
                p.delete(key)
            deletions = await p.execute()

        return [ { "key": key, "deleted": bool(deletion) } for key, deletion in zip(keys, deletions) ]

    async def _exists(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        # `EXISTS k1 k2 ...` returns only a total count; use a pipeline for per-key flags.
        async with self.client.pipeline(transaction=False) as p:
            for key in keys:
                p.exists(key)
            existences = await p.execute()

        return [ { "key": key, "exists": bool(existence) } for key, existence in zip(keys, existences) ]

    def _decode_value(self, value: Any) -> Any:
        value = value.decode("utf-8") if isinstance(value, bytes) else value

        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        return None

    def _encode_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)

        if not isinstance(value, str):
            return str(value)

        return value

@register_kv_store_service(KeyValueStoreDriver.REDIS)
class RedisKeyValueStoreService(KeyValueStoreService):
    def __init__(self, id: str, config: RedisKeyValueStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[AsyncRedis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "redis" ]

    async def _start(self) -> None:
        self.client = self._create_client()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            await self.client.aclose()
            self.client = None

    async def _run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        return await RedisKeyValueStoreAction(action, self.client).run(context)

    def _create_client(self) -> AsyncRedis:
        from redis.asyncio import Redis

        if self.config.url:
            return Redis.from_url(self.config.url)

        scheme = "rediss" if self.config.secure else "redis"
        url = f"{scheme}://{self.config.host}:{self.config.port}/{self.config.database}"

        return Redis.from_url(url, password=self.config.password)
