from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.controller import RedisControllerQueueConfig, ControllerQueueDriver
from ..base import CommonControllerQueueService, InterruptCallback, register_controller_queue_service
from ..serialize import serialize_input
from mindor.core.utils.compat.asyncio import async_timeout
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.foundation.variable.size import parse_size
from mindor.core.logger import logging
import asyncio, json, ulid

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.asyncio.client import PubSub

class RedisStreamIterator:
    def __init__(self, client, stream_key: str, timeout: Optional[float]):
        self._client = client
        self._stream_key = stream_key
        self._timeout = timeout
        self._last_id = "0-0"

    def __aiter__(self):
        return self

    async def __anext__(self):
        async with async_timeout(self._timeout):
            while True:
                entry = await self._read_entry()

                if entry is None:
                    continue

                return self._handle_entry(entry)

    async def _read_entry(self):
        entries = await self._client.xread({ self._stream_key: self._last_id }, count=1, block=5000)

        if entries:
            entry_id, fields = entries[0][1][0]
            self._last_id = entry_id

            return self._decode_fields(fields)

        return None

    def _handle_entry(self, fields: dict):
        event = fields.get("event")

        if event == "chunk":
            data = fields.get("data", "")
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return data

        if event == "done":
            raise StopAsyncIteration

        if event == "error":
            raise RuntimeError(fields.get("data", "Unknown streaming error"))

    def _decode_fields(self, fields: dict) -> dict:
        def _decode(value):
            return value.decode("utf-8") if isinstance(value, bytes) else value
        return { _decode(key): _decode(value) for key, value in fields.items() }

@register_controller_queue_service(ControllerQueueDriver.REDIS)
class RedisControllerQueueService(CommonControllerQueueService):
    def __init__(self, config: RedisControllerQueueConfig):
        super().__init__(config)

        self.client: Optional[Redis] = None

        self._timeout: Optional[float] = None
        self._blob_ttl: int = 0
        self._max_blob_size: Optional[int] = None

    def _get_setup_requirements(self):
        return [ "redis>=5.0.0" ]

    async def _start(self) -> None:
        import redis.asyncio as aioredis

        self.client = aioredis.from_url(
            self._build_redis_url(),
            db=self.config.database,
            password=self.config.password,
            decode_responses=False,
        )

        self._timeout = self._resolve_timeout()
        self._blob_ttl = self._resolve_blob_ttl()
        self._max_blob_size = self._resolve_max_blob_size()

        await super()._start()

    async def _stop(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

        await super()._stop()

    async def _dispatch(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        on_interrupt: InterruptCallback
    ) -> Any:
        run_id = ulid.ulid()
        queue_key  = f"{self.config.name}:{workflow_id}"
        result_key = f"{queue_key}:{run_id}"
        resume_key = f"{result_key}:resume"
        blob_prefix = f"{queue_key}:{run_id}:blob:"

        blob_keys: List[str] = []
        pubsub = None

        try:
            serialized_input, blob_keys = await serialize_input(
                input,
                self.client,
                blob_prefix,
                ttl_seconds=self._blob_ttl,
                max_blob_size=self._max_blob_size,
            )
            message = json.dumps({
                "task_id": task_id,
                "run_id": run_id,
                "input": serialized_input,
            })

            pubsub = self.client.pubsub()
            await pubsub.subscribe(result_key)
            await self.client.lpush(queue_key, message)
        except BaseException:
            if blob_keys:
                try:
                    await self.client.delete(*blob_keys)
                except BaseException as e:
                    logging.warning("Failed to cleanup blob keys (%d keys): %s", len(blob_keys), e)
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(result_key)
                    await pubsub.aclose()
                except asyncio.CancelledError:
                    pass
            raise

        try:
            while True:
                result = await self._wait_for_message(pubsub)
                status = result.get("status", "failed")

                if status == "interrupted" and on_interrupt:
                    answer = await on_interrupt(result.get("interrupt", {}))
                    await self.client.publish(resume_key, json.dumps({ "answer": answer }, default=str))
                    continue

                if status == "streaming":
                    stream_key = result.get("stream_key")
                    return RedisStreamIterator(self.client, stream_key, self._timeout)

                if status == "failed":
                    raise RuntimeError(result.get("error", "Unknown error from queue worker"))

                return result.get("output")
        except TimeoutError:
            raise TimeoutError(f"Queue dispatch timed out after {self.config.timeout} waiting for result") from None
        finally:
            try:
                await pubsub.unsubscribe(result_key)
                await pubsub.aclose()
            except asyncio.CancelledError:
                pass

    def _build_redis_url(self) -> str:
        if not self.config.url:
            scheme = "rediss" if self.config.secure else "redis"
            return f"{scheme}://{self.config.host}:{self.config.port}"

        return self.config.url

    def _resolve_timeout(self) -> Optional[float]:
        timeout = parse_duration(self.config.timeout)
        
        if timeout > 0:
            return timeout
        
        return None

    def _resolve_blob_ttl(self) -> int:
        if self.config.blob_ttl is not None:
            return int(parse_duration(self.config.blob_ttl))

        return 3600

    def _resolve_max_blob_size(self) -> Optional[int]:
        if self.config.max_blob_size is not None:
            return parse_size(self.config.max_blob_size)

        return None

    async def _wait_for_message(self, pubsub: PubSub) -> Dict[str, Any]:
        async with async_timeout(self._timeout):
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                return json.loads(message["data"])
