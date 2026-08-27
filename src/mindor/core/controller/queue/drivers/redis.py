from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional
from mindor.dsl.schema.controller import RedisControllerQueueConfig, ControllerQueueDriver
from mindor.core.foundation.variable.codec import VariableCodec
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.variable.size import parse_size
from mindor.core.utils.compat.asyncio import async_timeout
from mindor.core.logger import logging
from ..base import CommonControllerQueueService, InterruptCallback, register_controller_queue_service
from ..codec import QueueCodec, RedisStreamMeta
from ..stream import RedisInboundStream, RedisOutboundStream
import asyncio, json, ulid

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.asyncio.client import PubSub

_PROTOCOL_VERSION = "queue.v2"

@register_controller_queue_service(ControllerQueueDriver.REDIS)
class RedisControllerQueueService(CommonControllerQueueService):
    def __init__(self, config: RedisControllerQueueConfig):
        super().__init__(config)

        self.client: Optional[Redis] = None

        self._timeout: Optional[float] = None
        self._blob_ttl: int = 0
        self._max_blob_size: Optional[int] = None
        self._inline_bytes_threshold: int = 0
        self._max_stream_length: Optional[int] = None

    def _get_setup_requirements(self):
        return ["redis>=5.0.0"]

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
        self._inline_bytes_threshold = int(parse_size(self.config.inline_bytes_threshold))
        self._max_stream_length = self.config.max_stream_length

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
        on_interrupt: InterruptCallback,
    ) -> Any:
        run_id = ulid.ulid()
        queue_key   = f"{self.config.name}:{workflow_id}"
        result_key  = f"{queue_key}:{run_id}"
        resume_key  = f"{result_key}:resume"
        blob_prefix = f"{queue_key}:{run_id}:blob:"
        in_stream_prefix = f"{queue_key}:{run_id}:instream:"
        out_stream_prefix = f"{queue_key}:{run_id}:outstream:"

        # Codec for encoding input; stream markers get instream:* keys.
        input_codec = QueueCodec(
            client=self.client,
            blob_prefix=blob_prefix,
            stream_prefix=in_stream_prefix,
            blob_ttl=self._blob_ttl,
            result_ttl=self._blob_ttl,
            inline_bytes_threshold=self._inline_bytes_threshold,
            max_blob_size=self._max_blob_size,
        )

        # Codec for decoding output; stream markers materialize as RedisInboundStream-backed resources.
        output_codec = QueueCodec(
            client=self.client,
            blob_prefix=blob_prefix,
            stream_prefix=out_stream_prefix,
            blob_ttl=self._blob_ttl,
            result_ttl=self._blob_ttl,
            inline_bytes_threshold=self._inline_bytes_threshold,
            max_blob_size=self._max_blob_size,
            stream_factory=self._create_stream_factory(),
        )

        blob_keys: List[str] = []
        producer_tasks: List[asyncio.Task] = []
        pubsub = None

        try:
            input, blob_keys, streams_meta = await input_codec.encode_input(input)

            # Spawn XADD producers for any streams that flow into the worker.
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

            message = json.dumps({
                "protocol": _PROTOCOL_VERSION,
                "task_id": task_id,
                "run_id": run_id,
                "input": input,
                "streams": { stream_id: self._serialize_meta(meta_dict) for stream_id, meta_dict in streams_meta.items() },
            })

            pubsub = self.client.pubsub()
            await pubsub.subscribe(result_key)
            await self.client.lpush(queue_key, message)
        except BaseException:
            for task in producer_tasks:
                task.cancel()

            if blob_keys:
                try:
                    await self.client.delete(*blob_keys)
                except BaseException as e:
                    logging.warning("Failed to cleanup blob keys (%d): %s", len(blob_keys), e)

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
                    await self.client.publish(resume_key, json.dumps({"answer": answer}, default=str))
                    continue

                if status == "failed":
                    raise RuntimeError(result.get("error", "Unknown error from queue worker"))

                # `completed` or `streaming` — both carry an encoded `output` tree.
                output = await output_codec.decode_output(result.get("output"), result.get("streams") or {})

                return output
        except TimeoutError:
            raise TimeoutError(
                f"Queue dispatch timed out after {self.config.timeout} waiting for result"
            ) from None
        finally:
            try:
                await pubsub.unsubscribe(result_key)
                await pubsub.aclose()
            except asyncio.CancelledError:
                pass

            for task in producer_tasks:
                if not task.done():
                    task.cancel()

    async def _cancel(self, task_id: str) -> None:
        cancel_key = f"{self.config.name}:cancel"
        await self.client.publish(cancel_key, json.dumps({"task_id": task_id}))

    async def _publish_stream(self, meta: RedisStreamMeta, source: Any) -> None:
        """Publish chunks from `source` to the Redis stream identified by `meta`."""
        stream = RedisOutboundStream(
            client=self.client,
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

    def _create_stream_factory(self):
        codec = VariableCodec()

        def factory(meta: RedisStreamMeta):
            stream = RedisInboundStream(client=self.client, meta=meta, codec=codec)
            return stream.build_resource()

        return factory

    def _build_redis_url(self) -> str:
        if not self.config.url:
            scheme = "rediss" if self.config.secure else "redis"
            return f"{scheme}://{self.config.host}:{self.config.port}"

        return self.config.url

    def _resolve_timeout(self) -> Optional[float]:
        timeout = parse_time(self.config.timeout)

        if timeout > 0:
            return timeout

        return None

    def _resolve_blob_ttl(self) -> int:
        if self.config.blob_ttl is not None:
            return int(parse_time(self.config.blob_ttl))

        return 3600

    def _resolve_max_blob_size(self) -> Optional[int]:
        if self.config.max_blob_size is not None:
            return parse_size(self.config.max_blob_size)

        return None

    async def _wait_for_message(self, pubsub: "PubSub") -> Dict[str, Any]:
        async with async_timeout(self._timeout):
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                return json.loads(message["data"])

    @staticmethod
    def _serialize_meta(meta_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Strip local-only fields (source) before shipping meta in the queue message."""
        return { key: value for key, value in meta_dict.items() if key != "source" }
