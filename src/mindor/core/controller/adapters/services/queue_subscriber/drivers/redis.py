from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional
from mindor.core.foundation.variable.codec import VariableCodec
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.variable.size import parse_size
from mindor.dsl.schema.controller import RedisQueueSubscriberControllerAdapterConfig, QueueSubscriberDriver
from mindor.core.controller.base import TaskState, TaskStatus
from mindor.core.controller.queue.codec import QueueCodec, RedisStreamMeta
from mindor.core.controller.queue.stream import RedisInboundStream, RedisOutboundStream
from mindor.core.controller.queue.errors import (
    BlobNotFoundError,
    BlobCorruptedError,
    BlobUnauthorizedError,
    UnsupportedProtocolError,
)
from mindor.core.logger import logging
from ..base import CommonQueueSubscriberControllerAdapterService, register_queue_subscriber_controller_adapter_service
import asyncio, json, ulid

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

_PROTOCOL_VERSION = "queue.v2"

@register_queue_subscriber_controller_adapter_service(QueueSubscriberDriver.REDIS)
class RedisCommonQueueSubscriberControllerAdapterService(CommonQueueSubscriberControllerAdapterService):
    def __init__(
        self,
        config: RedisQueueSubscriberControllerAdapterConfig,
        controller: ControllerService,
        daemon: bool,
    ):
        super().__init__(config, controller, daemon)

        self._client = None
        self._workers: List[asyncio.Task] = []
        self._stop_event: asyncio.Event = asyncio.Event()
        self._worker_id: str = config.worker_id or ulid.ulid()
        self._active_task_ids: set[str] = set()

        self._blob_ttl: int = 0
        self._result_ttl: int = 0
        self._inline_bytes_threshold: int = 0
        self._max_blob_size: Optional[int] = None
        self._max_stream_length: Optional[int] = None

    def _get_setup_requirements(self):
        return ["redis>=5.0.0"]

    async def _serve(self) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(
            self._build_redis_url(),
            db=self.config.database,
            password=self.config.password,
            decode_responses=False,
        )

        self._blob_ttl = int(parse_time(self.config.blob_ttl)) if self.config.blob_ttl is not None else 3600
        self._result_ttl = int(parse_time(self.config.result_ttl))
        self._inline_bytes_threshold = int(parse_size(self.config.inline_bytes_threshold))
        self._max_blob_size = parse_size(self.config.max_blob_size) if self.config.max_blob_size is not None else None
        self._max_stream_length = self.config.max_stream_length

        workflows = self.config.workflows or list(self.controller.workflow_schemas.keys())
        queue_keys = [f"{self.config.name}:{workflow_id}" for workflow_id in workflows]
        logging.info(
            "Queue subscriber started: %s (queues: %s, workers: %d)",
            self._build_redis_url(),
            ", ".join(queue_keys),
            self.config.max_concurrent_count,
        )

        self._workers.append(asyncio.create_task(self._cancel_listener_loop()))

        for index in range(self.config.max_concurrent_count):
            task = asyncio.create_task(self._consumer_loop(index, queue_keys))
            self._workers.append(task)

        try:
            await asyncio.gather(*self._workers, return_exceptions=True)
        finally:
            await self._client.aclose()
            self._client = None

    async def _shutdown(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()

    async def _consumer_loop(self, worker_index: int, queue_keys: List[str]) -> None:
        while not self._stop_event.is_set():
            try:
                result = await self._client.brpop(queue_keys, timeout=int(parse_time(self.config.pop_timeout)))

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
        run_id = message.get("run_id")
        protocol = message.get("protocol")

        result_key  = f"{self.config.name}:{workflow_id}:{run_id}"
        resume_key  = f"{result_key}:resume"
        blob_prefix = f"{self.config.name}:{workflow_id}:{run_id}:blob:"
        in_stream_prefix = f"{self.config.name}:{workflow_id}:{run_id}:instream:"
        out_stream_prefix = f"{self.config.name}:{workflow_id}:{run_id}:outstream:"

        if protocol != _PROTOCOL_VERSION:
            state = TaskState(
                task_id=task_id or "",
                status=TaskStatus.FAILED,
                error=f"unsupported queue protocol: {protocol!r} (expected {_PROTOCOL_VERSION!r})",
            )
            await self._publish_terminal_result(workflow_id, task_id, run_id, state, {})
            return

        input_codec = QueueCodec(
            client=self._client,
            blob_prefix=blob_prefix,
            stream_prefix=in_stream_prefix,
            blob_ttl=self._blob_ttl,
            result_ttl=self._result_ttl,
            inline_bytes_threshold=self._inline_bytes_threshold,
            max_blob_size=self._max_blob_size,
            stream_factory=self._create_stream_factory(),
        )
        output_codec = QueueCodec(
            client=self._client,
            blob_prefix=blob_prefix,
            stream_prefix=out_stream_prefix,
            blob_ttl=self._blob_ttl,
            result_ttl=self._result_ttl,
            inline_bytes_threshold=self._inline_bytes_threshold,
            max_blob_size=self._max_blob_size,
        )

        try:
            input = await input_codec.decode_input(message.get("input", {}), message.get("streams") or {})
        except (BlobNotFoundError, BlobCorruptedError, BlobUnauthorizedError, UnsupportedProtocolError) as e:
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=str(e))
            await self._publish_terminal_result(workflow_id, task_id, run_id, state, {})
            return

        async def _on_interrupt(interrupt):
            # Subscribe before publishing so the dispatcher's resume publish
            # cannot race past us and be lost.
            pubsub = self._client.pubsub()
            await pubsub.subscribe(resume_key)
            try:
                state = TaskState(task_id=task_id, status=TaskStatus.INTERRUPTED, interrupt=interrupt)
                await self._publish_interrupt(workflow_id, task_id, run_id, state)
                return await self._read_resume(pubsub)
            finally:
                await pubsub.unsubscribe(resume_key)
                await pubsub.aclose()

        self._active_task_ids.add(task_id)

        try:
            state = await self.controller.run_workflow(
                workflow_id,
                input,
                task_id=task_id,
                wait_for_completion=True,
                on_interrupt=_on_interrupt,
            )
        except Exception as e:
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=str(e))
        finally:
            self._active_task_ids.discard(task_id)

        await self._publish_output(workflow_id, task_id, run_id, state, output_codec)

    async def _publish_output(
        self,
        workflow_id: str,
        task_id: str,
        run_id: str,
        state: TaskState,
        output_codec: QueueCodec,
    ) -> None:
        result_key = f"{self.config.name}:{workflow_id}:{run_id}"

        if state.status == TaskStatus.FAILED:
            await self._publish_terminal_result(workflow_id, task_id, run_id, state, {})
            return

        if state.status != TaskStatus.COMPLETED:
            # Cancelled / other non-terminal — publish as failed.
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=f"task ended with status {state.status.value}")
            await self._publish_terminal_result(workflow_id, task_id, run_id, state, {})
            return

        try:
            output, _, streams_meta = await output_codec.encode_output(state.output)
        except Exception as e:
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=str(e))
            await self._publish_terminal_result(workflow_id, task_id, run_id, state, {})
            return

        if not streams_meta:
            # Pure value — publish the terminal result now, then persist for readers of result_key.
            payload = {
                "protocol": _PROTOCOL_VERSION,
                "task_id": task_id,
                "run_id": run_id,
                "status": TaskStatus.COMPLETED.value,
                "worker_id": self._worker_id,
                "output": output,
                "streams": {},
            }
            await self._store_and_publish(result_key, payload)
            return

        # Streaming output — publish the marker payload first, then drive producers.
        payload = {
            "protocol": _PROTOCOL_VERSION,
            "task_id": task_id,
            "run_id": run_id,
            "status": "streaming",
            "worker_id": self._worker_id,
            "output": output,
            "streams": { stream_id: self._serialize_meta(meta_dict) for stream_id, meta_dict in streams_meta.items() },
        }
        await self._store_and_publish(result_key, payload)

        # Drive one XADD producer per registered stream.
        producer_tasks = []
        for stream_id, meta_dict in streams_meta.items():
            meta = RedisStreamMeta(
                stream_id=stream_id,
                kind=meta_dict["kind"],
                content_type=meta_dict.get("content_type"),
                filename=meta_dict.get("filename"),
                size=meta_dict.get("size"),
                attrs=meta_dict.get("attrs"),
                stream_key=meta_dict["stream_key"],
            )
            producer_tasks.append(
                asyncio.create_task(self._publish_stream(meta, meta_dict["source"]))
            )

        # Wait so we don't move on to another task before the producers finish;
        # keeps chunk streams alive for the duration of this worker slot.
        await asyncio.gather(*producer_tasks, return_exceptions=True)

    async def _publish_stream(self, meta: RedisStreamMeta, source: Any) -> None:
        stream = RedisOutboundStream(
            client=self._client,
            meta=meta,
            codec=VariableCodec(),
            inline_bytes_threshold=self._inline_bytes_threshold,
            blob_ttl=self._blob_ttl,
            max_stream_length=self._max_stream_length,
        )

        try:
            async for chunk in source:
                await stream.push_chunk(chunk)
            await stream.push_end()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            try:
                await stream.push_abort(str(e))
            except Exception:  # pragma: no cover - best effort
                pass
        finally:
            if self._result_ttl > 0:
                try:
                    await self._client.expire(meta.stream_key, self._result_ttl)
                except Exception:  # pragma: no cover
                    pass
            if hasattr(source, "aclose"):
                try:
                    await source.aclose()
                except Exception:  # pragma: no cover
                    pass

    def _create_stream_factory(self):
        codec = VariableCodec()

        def factory(meta: RedisStreamMeta):
            stream = RedisInboundStream(client=self._client, meta=meta, codec=codec)
            return stream.build_resource()

        return factory

    async def _publish_interrupt(self, workflow_id: str, task_id: str, run_id: str, state: TaskState) -> None:
        result_key = f"{self.config.name}:{workflow_id}:{run_id}"
        payload = {
            "protocol": _PROTOCOL_VERSION,
            "task_id": task_id,
            "run_id": run_id,
            "status": TaskStatus.INTERRUPTED.value,
            "worker_id": self._worker_id,
            "interrupt": {
                "job_id": state.interrupt.job_id if state.interrupt else "",
                "run_id": state.interrupt.run_id if state.interrupt else "",
                "phase": state.interrupt.phase if state.interrupt else "",
                "message": state.interrupt.message if state.interrupt else None,
                "metadata": state.interrupt.metadata if state.interrupt else None,
            },
        }
        # Interrupts are transient — only publish, do not persist.
        await self._client.publish(result_key, json.dumps(payload, default=str))

    async def _publish_terminal_result(
        self,
        workflow_id: str,
        task_id: str,
        run_id: str,
        state: TaskState,
        streams: Dict[str, Any],
    ) -> None:
        result_key = f"{self.config.name}:{workflow_id}:{run_id}"
        payload: Dict[str, Any] = {
            "protocol": _PROTOCOL_VERSION,
            "task_id": task_id,
            "run_id": run_id,
            "status": state.status.value,
            "worker_id": self._worker_id,
            "streams": streams,
        }
        if state.status == TaskStatus.FAILED:
            payload["error"] = state.error
        await self._store_and_publish(result_key, payload)

    async def _store_and_publish(self, result_key: str, payload: Dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        if self._result_ttl > 0:
            await self._client.setex(result_key, self._result_ttl, serialized)
        else:
            await self._client.set(result_key, serialized)
        await self._client.publish(result_key, serialized)

    async def _cancel_listener_loop(self) -> None:
        cancel_key = f"{self.config.name}:cancel"
        pubsub = self._client.pubsub()
        try:
            await pubsub.subscribe(cancel_key)
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                task_id = data.get("task_id")
                if not task_id or task_id not in self._active_task_ids:
                    continue
                try:
                    await self.controller.cancel_workflow(task_id, wait_for_completion=False)
                except Exception as e:
                    logging.warning("Failed to cancel task %s: %s", task_id, e)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(cancel_key)
                await pubsub.aclose()
            except Exception:
                pass

    async def _read_resume(self, pubsub) -> Any:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                return data.get("answer")

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

    @staticmethod
    def _serialize_meta(meta_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Strip local-only fields (source) before shipping meta in the queue message."""
        return { key: value for key, value in meta_dict.items() if key != "source" }
