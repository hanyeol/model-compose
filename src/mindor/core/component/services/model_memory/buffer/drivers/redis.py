from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Any
from mindor.dsl.schema.component import RedisModelMemoryBufferConfig, ModelMemoryBufferDriver
from ..base import ModelMemoryBuffer, register_model_memory_buffer
import asyncio
import json
import ulid

if TYPE_CHECKING:
    import redis.asyncio as aioredis

@register_model_memory_buffer(ModelMemoryBufferDriver.REDIS)
class RedisModelMemoryBuffer(ModelMemoryBuffer):

    def __init__(self, config: RedisModelMemoryBufferConfig):
        super().__init__()

        self.config: RedisModelMemoryBufferConfig = config
        self.client: Optional[aioredis.Redis] = None

        self._node_id: str = ulid.ulid()
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._listener_task: Optional[asyncio.Task] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "redis" ]

    async def setup(self) -> None:
        import redis.asyncio as aioredis

        if self.config.url:
            self.client = aioredis.from_url(self.config.url)
        else:
            self.client = aioredis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.database,
                password=self.config.password,
                ssl=self.config.secure,
            )

        self._pubsub = self.client.pubsub()
        await self._pubsub.subscribe(self._updates_channel())

        self._listener_task = asyncio.create_task(self._listen_updates())

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self._updates_channel())
            await self._pubsub.aclose()
            self._pubsub = None
        if self.client:
            await self.client.aclose()
            self.client = None
        self._sessions.clear()

    async def _listen_updates(self) -> None:
        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                if data["node"] == self._node_id:
                    continue
                session_id = data["session"]
                session = self._sessions.get(session_id)
                if session is not None:
                    session.settled_turns = await self._read_turns(session_id)
                    session.clear_pending()
        except asyncio.CancelledError:
            pass

    async def _on_update_turns(self, session_id: str) -> None:
        await super()._on_update_turns(session_id)

        message = json.dumps({"node": self._node_id, "session": session_id})
        await self.client.publish(self._updates_channel(), message)

    async def _read_turns(self, session_id: str) -> List[List[Any]]:
        raw = await self.client.get(self._session_key(session_id, "turns"))
        if raw is None:
            return []
        return json.loads(raw)

    async def _write_turns(self, session_id: str, turns: List[List[Any]]) -> None:
        await self.client.set(
            self._session_key(session_id, "turns"),
            json.dumps(turns, ensure_ascii=False),
        )

    async def _remove_all(self, session_id: str) -> None:
        await self.client.delete(self._session_key(session_id, "turns"))

    def _session_key(self, session_id: str, suffix: str) -> str:
        return f"{self.config.prefix}{session_id}:{suffix}"

    def _updates_channel(self) -> str:
        return f"{self.config.prefix}__updates__"
