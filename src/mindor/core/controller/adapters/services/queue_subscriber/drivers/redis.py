from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.dsl.schema.controller import RedisQueueSubscriberControllerAdapterConfig, QueueSubscriberDriver
from mindor.core.controller.base import TaskState, TaskStatus
from mindor.core.controller.queue.serialize import deserialize_input
from mindor.core.controller.queue.errors import BlobNotFoundError, BlobCorruptedError, BlobUnauthorizedError
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from ..base import CommonQueueSubscriberControllerAdapterService, register_queue_subscriber_controller_adapter_service
import asyncio, json, ulid

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

@register_queue_subscriber_controller_adapter_service(QueueSubscriberDriver.REDIS)
class RedisCommonQueueSubscriberControllerAdapterService(CommonQueueSubscriberControllerAdapterService):
    def __init__(
        self,
        config: RedisQueueSubscriberControllerAdapterConfig,
        controller: ControllerService,
        daemon: bool
    ):
        super().__init__(config, controller, daemon)

        self._client = None
        self._workers: List[asyncio.Task] = []
        self._stop_event: asyncio.Event = asyncio.Event()
        self._worker_id: str = config.worker_id or ulid.ulid()

    def _get_setup_requirements(self):
        return [ "redis>=5.0.0" ]

    async def _serve(self) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(
            self._build_redis_url(),
            db=self.config.database,
            password=self.config.password,
            decode_responses=False,
        )

        workflows = self.config.workflows or list(self.controller.workflow_schemas.keys())
        queue_keys = [ f"{self.config.name}:{workflow_id}" for workflow_id in workflows ]
        logging.info("Queue subscriber started: %s (queues: %s, workers: %d)", self._build_redis_url(), ", ".join(queue_keys), self.config.max_concurrent_count)

        for index in range(self.config.max_concurrent_count):
            task = asyncio.create_task(self._consumer_loop(index, queue_keys))
            self._workers.append(task)

        try:
            await asyncio.gather(*self._workers)
        finally:
            await self._client.aclose()
            self._client = None

    async def _shutdown(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()

    async def _consumer_loop(self, worker_index: int, queue_keys: list[str]) -> None:
        while not self._stop_event.is_set():
            try:
                result = await self._client.brpop(queue_keys, timeout=int(parse_duration(self.config.pop_timeout)))

                if result is None:
                    continue

                queue_key, raw_message = result
                workflow_id = self._workflow_id_from_queue_key(queue_key.decode("utf-8"))

                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                await self._handle_workflow_task(workflow_id, message)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _handle_workflow_task(self, workflow_id: str, message: Dict[str, Any]) -> None:
        task_id = message.get("task_id")
        run_id  = message.get("run_id")
        input   = message.get("input", {})
        result_key  = f"{self.config.name}:{workflow_id}:{run_id}"
        resume_key  = f"{result_key}:resume"
        blob_prefix = f"{self.config.name}:{workflow_id}:{run_id}:blob:"

        try:
            input = await deserialize_input(input, self._client, blob_prefix)
        except (BlobNotFoundError, BlobCorruptedError, BlobUnauthorizedError) as e:
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=str(e))
            await self._publish_result(workflow_id, task_id, run_id, state)
            return

        async def _on_interrupt(interrupt):
            # Subscribe before publishing so the dispatcher's resume publish
            # cannot race past us and be lost.
            pubsub = self._client.pubsub()
            await pubsub.subscribe(resume_key)
            try:
                state = TaskState(task_id=task_id, status=TaskStatus.INTERRUPTED, interrupt=interrupt)
                await self._publish_result(workflow_id, task_id, run_id, state)
                return await self._read_resume(pubsub)
            finally:
                await pubsub.unsubscribe(resume_key)
                await pubsub.aclose()

        try:
            state = await self.controller.run_workflow(
                workflow_id,
                input,
                wait_for_completion=True,
                on_interrupt=_on_interrupt
            )
        except Exception as e:
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=str(e))

        if state.status == TaskStatus.COMPLETED and isinstance(state.output, (StreamIterator, AsyncIterator)):
            await self._publish_stream_result(workflow_id, task_id, run_id, state)
        else:
            await self._publish_result(workflow_id, task_id, run_id, state)

    async def _read_resume(self, pubsub) -> Any:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                return data.get("answer")

    async def _publish_result(self, workflow_id: str, task_id: str, run_id: str, state: TaskState) -> None:
        result_key = f"{self.config.name}:{workflow_id}:{run_id}"

        result = json.dumps({
            "task_id": task_id,
            "run_id": run_id,
            "status": state.status.value,
            "worker_id": self._worker_id,
            **(self._get_task_output(state) or {}),
        }, default=str)

        result_ttl = int(parse_duration(self.config.result_ttl))
        if result_ttl > 0:
            await self._client.setex(result_key, result_ttl, result)
        else:
            await self._client.set(result_key, result)

        await self._client.publish(result_key, result)

    async def _publish_stream_result(self, workflow_id: str, task_id: str, run_id: str, state: TaskState) -> None:
        result_key = f"{self.config.name}:{workflow_id}:{run_id}"
        stream_key = f"{result_key}:stream"
        result_ttl = int(parse_duration(self.config.result_ttl))

        result = json.dumps({
            "task_id": task_id,
            "run_id": run_id,
            "status": "streaming",
            "worker_id": self._worker_id,
            "stream_key": stream_key,
        })
        await self._client.publish(result_key, result)

        try:
            async for chunk in state.output:
                data = chunk if isinstance(chunk, str) else json.dumps(chunk, default=str, ensure_ascii=False)
                await self._client.xadd(stream_key, { "event": "chunk", "data": data })

            await self._client.xadd(stream_key, { "event": "done" })
        except Exception as e:
            await self._client.xadd(stream_key, { "event": "error", "data": str(e) })
        finally:
            if result_ttl > 0:
                await self._client.expire(stream_key, result_ttl)

            if hasattr(state.output, 'aclose'):
                await state.output.aclose()

    def _build_redis_url(self) -> str:
        if not self.config.url:
            scheme = "rediss" if self.config.secure else "redis"
            return f"{scheme}://{self.config.host}:{self.config.port}"

        return self.config.url

    def _workflow_id_from_queue_key(self, queue_key: str) -> str:
        prefix = self.config.name + ":"

        if queue_key.startswith(prefix):
            return queue_key[len(prefix):]

        return queue_key

    def _get_task_output(self, state: TaskState) -> Optional[Dict[str, Any]]:
        if state.status == TaskStatus.INTERRUPTED and state.interrupt:
            return { "interrupt": {
                "job_id": state.interrupt.job_id,
                "phase": state.interrupt.phase,
                "message": state.interrupt.message,
                "metadata": state.interrupt.metadata,
            }}

        if state.status == TaskStatus.FAILED:
            return { "error": state.error }

        if state.status == TaskStatus.COMPLETED:
            return { "output": state.output }

        return None
