from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any
from mindor.dsl.schema.controller import RedisQueueSubscriberControllerAdapterConfig, QueueSubscriberDriver
from mindor.core.controller.base import TaskState, TaskStatus
from ..base import CommonQueueSubscriberControllerAdapterService, register_queue_subscriber_controller_adapter_service
import asyncio, json, ulid

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

@register_queue_subscriber_controller_adapter_service(QueueSubscriberDriver.REDIS)
class RedisCommonQueueSubscriberControllerAdapterService(CommonQueueSubscriberControllerAdapterService):
    def __init__(self, config: RedisQueueSubscriberControllerAdapterConfig, controller: ControllerService, daemon: bool):
        super().__init__(config, controller, daemon)
        self._redis = None
        self._workers: list[asyncio.Task] = []
        self._stop_event: asyncio.Event = asyncio.Event()
        self._worker_id: str = config.worker_id or ulid.ulid()

    async def _serve(self) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(
            self._build_redis_url(),
            db=self.config.db,
            password=self.config.password,
            decode_responses=True,
        )

        queue_keys = [ f"{self.config.queue_name}:{workflow}" for workflow in self.config.workflows ]
        for index in range(self.config.max_concurrent):
            task = asyncio.create_task(self._consumer_loop(index, queue_keys))
            self._workers.append(task)

        try:
            await asyncio.gather(*self._workers)
        finally:
            await self._redis.aclose()
            self._redis = None

    async def _shutdown(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()

    async def _consumer_loop(self, worker_index: int, queue_keys: list[str]) -> None:
        while not self._stop_event.is_set():
            try:
                result = await self._redis.brpop(queue_keys, timeout=self.config.pop_timeout)

                if result is None:
                    continue

                queue_key, raw_message = result
                workflow_id = self._workflow_id_from_queue_key(queue_key)

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

        try:
            state = await self.controller.run_workflow(workflow_id, input, wait_for_completion=True)
            result = {
                "task_id": task_id,
                "run_id": run_id,
                "status": state.status.value,
                "worker_id": self._worker_id,
                **(self._build_result_detail(state) or {}),
            }
        except Exception as e:
            result = {
                "task_id": task_id,
                "run_id": run_id,
                "status": "failed",
                "error": str(e),
                "worker_id": self._worker_id,
            }

        await self._publish_result(run_id, result)

    def _build_redis_url(self) -> str:
        if not self.config.url:
            scheme = "rediss" if self.config.tls else "redis"
            return f"{scheme}://{self.config.host}:{self.config.port}"
        
        return self.config.url

    def _workflow_id_from_queue_key(self, queue_key: str) -> str:
        prefix = self.config.queue_name + ":"

        if queue_key.startswith(prefix):
            return queue_key[len(prefix):]

        return queue_key

    def _build_result_detail(self, state: TaskState) -> Optional[Dict[str, Any]]:
        if state.status == TaskStatus.INTERRUPTED and state.interrupt:
            return {
                "interrupt": {
                    "job_id": state.interrupt.job_id,
                    "phase": state.interrupt.phase,
                    "message": state.interrupt.message,
                    "metadata": state.interrupt.metadata,
                }
            }

        if state.status == TaskStatus.COMPLETED:
            return { "output": state.output }

        if state.status == TaskStatus.FAILED:
            return { "error": state.error }

        return None

    async def _publish_result(self, run_id: str, result: Dict[str, Any]) -> None:
        result_json = json.dumps(result, default=str)
        result_key = f"{self.config.result_prefix}{run_id}"

        if self.config.result_ttl > 0:
            await self._redis.setex(result_key, self.config.result_ttl, result_json)
        else:
            await self._redis.set(result_key, result_json)

        await self._redis.publish(result_key, result_json)
