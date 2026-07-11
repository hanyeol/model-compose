from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from mindor.dsl.schema.component import RedisKeyValueStoreComponentConfig
from mindor.dsl.schema.action import KeyValueStoreActionConfig, RedisKeyValueStoreActionConfig
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

    async def _get(self, key: Union[str, List[str]]) -> Dict[str, Any]:
        if isinstance(key, list):
            raws = await self.client.mget(key) if key else []
            return { "values": [ self._decode_value(raw) for raw in raws ] }

        return { "value": self._decode_value(await self.client.get(key)) }

    def _decode_value(self, raw: Any) -> Any:
        if raw is None:
            return None

        value = raw.decode("utf-8") if isinstance(raw, bytes) else raw

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def _set(self, key: str, value: Any, ttl: Optional[int]) -> Dict[str, Any]:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif not isinstance(value, str):
            value = str(value)

        if ttl is not None:
            result = await self.client.setex(key, ttl, value)
        else:
            result = await self.client.set(key, value)

        return { "success": bool(result) }

    async def _delete(self, key: Union[str, List[str]]) -> Dict[str, Any]:
        if isinstance(key, list):
            count = await self.client.delete(*key) if key else 0
        else:
            count = await self.client.delete(key)

        return { "count": count }

    async def _exists(self, key: Union[str, List[str]]) -> Dict[str, Any]:
        if isinstance(key, list):
            count = await self.client.exists(*key) if key else 0
            return { "count": count }

        return { "exists": bool(await self.client.exists(key)) }

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
