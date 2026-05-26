from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Any
from mindor.dsl.schema.controller import RedisControllerQueueConfig, ControllerQueueDriver
from ..base import CommonControllerQueueService, InterruptCallback, register_controller_queue_service
from mindor.core.foundation.compat.asyncio import async_timeout
from mindor.core.utils.time import parse_duration
import asyncio, json, ulid

class RedisStreamIterator:
    def __init__(self, client, stream_key: str, timeout: float):
        self._client = client
        self._stream_key = stream_key
        self._timeout = timeout if timeout > 0 else None
        self._last_id = "0-0"

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            async with async_timeout(self._timeout):
                while True:
                    entry = await self._read_entry()

                    if entry is None:
                        continue

                    return self._handle_entry(entry)
        except TimeoutError:
            raise TimeoutError(f"Stream read timed out after {self._timeout}s")

    async def _read_entry(self):
        entries = await self._client.xread(
            { self._stream_key: self._last_id },
            count=1, block=5000
        )

        if not entries:
            return None

        entry_id, fields = entries[0][1][0]
        self._last_id = entry_id

        return self._decode_fields(fields)

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

        self._client = None

    def _get_setup_requirements(self):
        return [ "redis>=5.0.0" ]

    async def _start(self) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(
            self._build_redis_url(),
            db=self.config.database,
            password=self.config.password,
            decode_responses=False,
        )

        await super()._start()

    async def _stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

        await super()._stop()

    async def _dispatch(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        on_interrupt: InterruptCallback
    ) -> Any:
        run_id = ulid.ulid()
        queue_key = f"{self.config.name}:{workflow_id}"
        result_key = f"{queue_key}:{run_id}"
        resume_key = f"{result_key}:resume"

        message = json.dumps({
            "task_id": task_id,
            "run_id": run_id,
            "input": input,
        }, default=str)

        pubsub = self._client.pubsub()
        await pubsub.subscribe(result_key)

        try:
            await self._client.lpush(queue_key, message)

            while True:
                result = await self._wait_for_message(pubsub)
                status = result.get("status", "failed")

                if status == "interrupted" and on_interrupt:
                    answer = await on_interrupt(result.get("interrupt", {}))
                    await self._client.publish(resume_key, json.dumps({ "answer": answer }, default=str))
                    continue

                if status == "streaming":
                    stream_key = result.get("stream_key")
                    return RedisStreamIterator(self._client, stream_key, parse_duration(self.config.timeout).total_seconds())

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

    async def _wait_for_message(self, pubsub) -> Dict[str, Any]:
        timeout_secs = parse_duration(self.config.timeout).total_seconds()
        timeout = timeout_secs if timeout_secs > 0 else None

        async with async_timeout(timeout):
            async for message in pubsub.listen():
                if message["type"] != b"message":
                    continue

                return json.loads(message["data"])
