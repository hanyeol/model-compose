from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Any
from mindor.dsl.schema.controller import RedisControllerQueueConfig, ControllerQueueDriver
from ..base import CommonControllerQueueService, InterruptCallback, register_controller_queue_service
import asyncio, json, ulid

@register_controller_queue_service(ControllerQueueDriver.REDIS)
class RedisControllerQueueService(CommonControllerQueueService):
    def __init__(self, config: RedisControllerQueueConfig):
        super().__init__(config)
        self._redis = None

    def _get_setup_requirements(self):
        return [ "redis>=5.0.0" ]

    async def _start(self) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(
            self._build_redis_url(),
            db=self.config.database,
            password=self.config.password,
            decode_responses=True,
        )

        await super()._start()

    async def _stop(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None

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

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(result_key)

        try:
            await self._redis.lpush(queue_key, message)

            while True:
                result = await self._wait_for_message(pubsub)
                status = result.get("status", "failed")

                if status == "interrupted" and on_interrupt:
                    answer = await on_interrupt(result.get("interrupt", {}))
                    await self._redis.publish(resume_key, json.dumps({"answer": answer}, default=str))
                    continue

                if status == "failed":
                    raise RuntimeError(result.get("error", "Unknown error from queue worker"))

                return result.get("output")
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
        timeout = self.config.timeout if self.config.timeout > 0 else None

        try:
            async with asyncio.timeout(timeout):
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue

                    return json.loads(message["data"])
        except TimeoutError:
            pass

        raise TimeoutError(f"Queue dispatch timed out after {self.config.timeout}s waiting for result")
