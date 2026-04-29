from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import RedisKeyValueStoreComponentConfig
from mindor.dsl.schema.action import KeyValueStoreActionConfig, RedisKeyValueStoreActionConfig, KeyValueStoreActionMethod
from ..base import KeyValueStoreService, KeyValueStoreDriver, register_kv_store_service
from ..base import ComponentActionContext
import json

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

class RedisKeyValueStoreAction:
    def __init__(self, config: RedisKeyValueStoreActionConfig):
        self.config: RedisKeyValueStoreActionConfig = config

    async def run(self, context: ComponentActionContext, client: AsyncRedis) -> Any:
        result = await self._dispatch(context, client)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, client: AsyncRedis) -> Dict[str, Any]:
        if self.config.method == KeyValueStoreActionMethod.GET:
            return await self._get(context, client)

        if self.config.method == KeyValueStoreActionMethod.SET:
            return await self._set(context, client)

        if self.config.method == KeyValueStoreActionMethod.DELETE:
            return await self._delete(context, client)

        if self.config.method == KeyValueStoreActionMethod.EXISTS:
            return await self._exists(context, client)

        raise ValueError(f"Unsupported key-value store action method: {self.config.method}")

    async def _get(self, context: ComponentActionContext, client: AsyncRedis) -> Dict[str, Any]:
        key = await context.render_variable(self.config.key)

        raw = await client.get(key)

        if raw is None:
            return { "value": None }

        value = raw.decode("utf-8") if isinstance(raw, bytes) else raw

        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass

        return { "value": value }

    async def _set(self, context: ComponentActionContext, client: AsyncRedis) -> Dict[str, Any]:
        key   = await context.render_variable(self.config.key)
        value = await context.render_variable(self.config.value)
        ttl   = await context.render_variable(self.config.ttl)

        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif not isinstance(value, str):
            value = str(value)

        if ttl is not None:
            ttl = int(ttl)
            result = await client.setex(key, ttl, value)
        else:
            result = await client.set(key, value)

        return { "success": bool(result) }

    async def _delete(self, context: ComponentActionContext, client: AsyncRedis) -> Dict[str, Any]:
        key = await context.render_variable(self.config.key)

        count = await client.delete(key)

        return { "count": count }

    async def _exists(self, context: ComponentActionContext, client: AsyncRedis) -> Dict[str, Any]:
        key = await context.render_variable(self.config.key)

        count = await client.exists(key)

        return { "exists": bool(count) }

@register_kv_store_service(KeyValueStoreDriver.REDIS)
class RedisKeyValueStoreService(KeyValueStoreService):
    def __init__(self, id: str, config: RedisKeyValueStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[AsyncRedis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "redis" ]

    async def _serve(self) -> None:
        self.client = self._create_client()

    async def _shutdown(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def _run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        return await RedisKeyValueStoreAction(action).run(context, self.client)

    def _create_client(self) -> AsyncRedis:
        from redis.asyncio import Redis

        if self.config.url:
            return Redis.from_url(self.config.url)

        scheme = "rediss" if self.config.secure else "redis"
        url = f"{scheme}://{self.config.host}:{self.config.port}/{self.config.database}"

        return Redis.from_url(url, password=self.config.password)
