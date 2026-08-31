"""End-to-end round-trip tests for the `queue.v2` codec upgrade of the
queue-subscribe adapter.

Brings up `RedisControllerQueueService` (dispatcher) and
`RedisCommonQueueSubscriberControllerAdapterService` (subscriber) against a
real Redis (`localhost:6379`), and verifies that Python types round-trip end
to end per `docs/specs/queue-subscribe-codec-spec.md`:

- `bytes` input → subscriber receives `bytes` (NOT `UploadFile`)
- `PIL.Image` input → subscriber receives an `ImageStreamResource` (or `PIL.Image`)
- `TextStreamResource` input → subscriber receives a `TextStreamResource`
- `bytes` output → dispatcher receives `bytes`
- Audio stream output with `attrs` → dispatcher receives `WavStreamResource`
  with `attrs` preserved
- Large `bytes` output → blob-offloaded then consumed on dispatch (no leak)
- Stream abort → dispatcher-side iterator raises `StreamAbortError`
- Nested `bytes` inside an OBJECT-kind stream chunk → preserved on both sides

The tests skip automatically when Redis is unreachable, and the whole module
skips when the `queue.v2` symbols do not yet exist in the codebase.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any, Awaitable, Callable, Dict, List, Optional

import pytest
from PIL import Image as PILImage

from mindor.core.controller.base import TaskState, TaskStatus
from mindor.core.controller.adapters.services.queue_subscriber.drivers.redis import (
    RedisCommonQueueSubscriberControllerAdapterService,
)
from mindor.core.controller.queue.drivers.redis import RedisControllerQueueService
from mindor.core.foundation.streaming.audio import WavStreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.dsl.schema.controller import (
    ControllerAdapterType,
    ControllerQueueDriver,
    QueueSubscriberDriver,
    RedisControllerQueueConfig,
    RedisQueueSubscriberControllerAdapterConfig,
)

# The whole module targets the queue.v2 codec surface. Skip cleanly if the
# implementation is not merged yet.
pytest.importorskip("mindor.core.controller.queue.codec")
pytest.importorskip("mindor.core.controller.queue.stream")


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def redis_available() -> bool:
    """Probe localhost Redis once per session; skip tests if unreachable."""
    import socket
    try:
        with socket.create_connection(("localhost", 6379), timeout=0.5):
            return True
    except (OSError, ConnectionRefusedError):
        return False


@pytest.fixture
def queue_name(request) -> str:
    import ulid
    return f"test-e2e-v2-{request.node.name}-{ulid.ulid()}"


WORKFLOW_ID = "wf-echo"


# ──────────────────────────────────────────────────────────────────────────────
# Dummy controller — configurable handler that records what it received
# ──────────────────────────────────────────────────────────────────────────────

class DummyController:
    def __init__(
        self,
        workflows: List[str],
        handler: Optional[
            Callable[[str, Dict[str, Any], Any], Awaitable[Any]]
        ] = None,
    ):
        self.workflow_schemas = {wf: None for wf in workflows}
        self._handler = handler or self._echo_handler
        self.received_inputs: List[Any] = []

    async def _echo_handler(self, workflow_id, input, on_interrupt):
        return {"echo": input}

    async def run_workflow(
        self,
        workflow_id: str,
        input: Any,
        task_id: Optional[str] = None,
        wait_for_completion: bool = True,
        on_interrupt: Any = None,
        session_id: Any = None,
        metadata: Any = None,
    ) -> TaskState:
        self.received_inputs.append(input)
        try:
            output = await self._handler(workflow_id, input, on_interrupt)
            return TaskState(
                task_id=task_id or "dummy",
                status=TaskStatus.COMPLETED,
                workflow_id=workflow_id,
                output=output,
            )
        except Exception as e:
            return TaskState(
                task_id=task_id or "dummy",
                status=TaskStatus.FAILED,
                workflow_id=workflow_id,
                error=str(e),
            )

    async def cancel_workflow(self, task_id: str, wait_for_completion: bool = True):
        return TaskState(task_id=task_id, status=TaskStatus.CANCELLING)


# ──────────────────────────────────────────────────────────────────────────────
# Wire-up helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _start_dispatcher(
    queue_name: str, **overrides
) -> RedisControllerQueueService:
    config = RedisControllerQueueConfig(
        driver=ControllerQueueDriver.REDIS,
        name=queue_name,
        timeout=overrides.pop("timeout", "10s"),
        max_blob_size=overrides.pop("max_blob_size", "50M"),
        blob_ttl=overrides.pop("blob_ttl", None),
        inline_bytes_threshold=overrides.pop("inline_bytes_threshold", "64B"),
        **overrides,
    )
    service = RedisControllerQueueService(config)
    await service._start()
    return service


async def _start_subscriber(
    queue_name: str, workflows: List[str], controller: DummyController
) -> RedisCommonQueueSubscriberControllerAdapterService:
    config = RedisQueueSubscriberControllerAdapterConfig(
        type=ControllerAdapterType.QUEUE_SUBSCRIBER,
        driver=QueueSubscriberDriver.REDIS,
        name=queue_name,
        workflows=workflows,
        pop_timeout="1s",
        max_concurrent_count=1,
    )
    service = RedisCommonQueueSubscriberControllerAdapterService(
        config=config,
        controller=controller,  # type: ignore[arg-type]
        daemon=True,
    )
    serve_task = asyncio.create_task(service._serve())
    await asyncio.sleep(0.1)
    service._serve_task = serve_task  # type: ignore[attr-defined]
    return service


async def _stop_subscriber(service) -> None:
    await service._shutdown()
    serve_task = getattr(service, "_serve_task", None)
    if serve_task is not None:
        try:
            await asyncio.wait_for(serve_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass


async def _no_leftover_blobs(queue_name: str) -> bool:
    """Return True when no blob keys remain under the queue namespace.

    Uses an ad-hoc Redis client so the check remains valid even after the
    dispatcher/subscriber under test have closed their own clients.
    """
    import redis.asyncio as aioredis
    client = aioredis.from_url("redis://localhost:6379", decode_responses=False)
    try:
        pattern = f"{queue_name}:*:blob:*".encode("utf-8")
        remaining = [k async for k in client.scan_iter(match=pattern)]
        return remaining == []
    finally:
        await client.aclose()


# ──────────────────────────────────────────────────────────────────────────────
# Input round-trip — types must survive dispatcher → subscriber
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_bytes_input_arrives_as_bytes(redis_available, queue_name):
    """`bytes` input must arrive as `bytes` (NOT `UploadFile`) on subscriber side."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={"blob": b"hello"},
            on_interrupt=None,
        )
        assert controller.received_inputs, "subscriber should receive input"
        received = controller.received_inputs[0]
        assert isinstance(received["blob"], bytes)
        assert received["blob"] == b"hello"
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()
        assert await _no_leftover_blobs(queue_name)


@pytest.mark.anyio
async def test_large_bytes_offloaded_and_cleaned(redis_available, queue_name):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(
        queue_name, inline_bytes_threshold="8B"
    )
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        payload = b"X" * (256 * 1024)  # 256 KB > 8 B threshold
        await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={"blob": payload},
            on_interrupt=None,
        )
        received = controller.received_inputs[0]
        assert received["blob"] == payload
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()
        # blob offload path must clean up after decode
        assert await _no_leftover_blobs(queue_name)


@pytest.mark.anyio
async def test_pil_image_input_becomes_stream_resource(redis_available, queue_name):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        img = PILImage.new("RGB", (4, 4), color=(0, 255, 0))
        await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={"img": img},
            on_interrupt=None,
        )
        received = controller.received_inputs[0]
        assert isinstance(received["img"], (ImageStreamResource, StreamResource))
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_text_stream_resource_input_preserved(redis_available, queue_name):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        text_stream = TextStreamResource("streamed", encoding="utf-8")
        await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={"stream": text_stream},
            on_interrupt=None,
        )
        received = controller.received_inputs[0]
        assert isinstance(received["stream"], StreamResource)
        assert (received["stream"].content_type or "").startswith("text/")
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


# ──────────────────────────────────────────────────────────────────────────────
# Output round-trip — types must survive subscriber → dispatcher
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_bytes_output_arrives_as_bytes(redis_available, queue_name):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    async def handler(workflow_id, input, on_interrupt):
        return {"blob": b"result-bytes"}

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={},
            on_interrupt=None,
        )
        assert isinstance(result["blob"], bytes)
        assert result["blob"] == b"result-bytes"
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_large_bytes_output_offload_and_cleanup(redis_available, queue_name):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    payload = b"Y" * (256 * 1024)

    async def handler(workflow_id, input, on_interrupt):
        return {"blob": payload}

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(
        queue_name, inline_bytes_threshold="8B"
    )
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={},
            on_interrupt=None,
        )
        assert result["blob"] == payload
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()
        # Both directions cleaned up.
        assert await _no_leftover_blobs(queue_name)


# ──────────────────────────────────────────────────────────────────────────────
# Streaming output
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_wav_stream_output_preserves_type_and_attrs(
    redis_available, queue_name
):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    async def wav_chunks():
        for chunk in (b"RIFF", b"WAVE", b"\x00\x01"):
            yield chunk

    async def handler(workflow_id, input, on_interrupt):
        return WavStreamResource(
            wav_chunks(),
            attrs={"sample_rate": 16000, "channels": 1},
            filename="voice.wav",
        )

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={},
            on_interrupt=None,
        )
        assert isinstance(result, WavStreamResource)
        assert getattr(result, "attrs", None) == {"sample_rate": 16000, "channels": 1}
        assert result.filename == "voice.wav"

        # Drain and verify chunk fidelity. `WavStreamResource` prepends a
        # streaming WAV header (44 bytes) built from `attrs` when the resource
        # sits on raw samples, so the original payload appears after the header.
        collected = b""
        async for chunk in result:
            collected += chunk
        assert collected.endswith(b"RIFFWAVE\x00\x01")
        assert collected.startswith(b"RIFF")  # WAV header prefix
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_bytes_stream_output_large_chunks_offloaded(
    redis_available, queue_name
):
    """Large per-chunk `bytes` payloads must offload to blobs and clean up."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    payload = b"Z" * (128 * 1024)

    async def chunks():
        yield payload
        yield payload

    async def handler(workflow_id, input, on_interrupt):
        return BytesStreamResource(payload + payload, content_type="application/octet-stream")

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(
        queue_name, inline_bytes_threshold="1KB"
    )
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={},
            on_interrupt=None,
        )
        collected = b""
        async for chunk in result:
            assert isinstance(chunk, bytes)
            collected += chunk
        assert collected == payload + payload
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()
        assert await _no_leftover_blobs(queue_name)


@pytest.mark.anyio
async def test_object_stream_chunks_roundtrip(redis_available, queue_name):
    """OBJECT-kind chunks (dicts) round-trip via VariableCodec encoding."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    from mindor.core.foundation.streaming.iterators import (
        StreamChunkIterator,
    )

    async def chunks():
        yield {"delta": {"content": "hi"}}
        yield {"delta": {"content": " there"}}

    async def handler(workflow_id, input, on_interrupt):
        return StreamChunkIterator(chunks())

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={},
            on_interrupt=None,
        )
        collected = []
        async for chunk in result:
            collected.append(chunk)
        assert collected == [
            {"delta": {"content": "hi"}},
            {"delta": {"content": " there"}},
        ]
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_stream_abort_surfaces_as_stream_abort_error(
    redis_available, queue_name
):
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    from mindor.core.controller.queue.errors import StreamAbortError
    from mindor.core.foundation.streaming.iterators import (
        StreamChunkIterator,
    )

    async def flaky_chunks():
        yield "partial"
        raise RuntimeError("upstream boom")

    async def handler(workflow_id, input, on_interrupt):
        return StreamChunkIterator(flaky_chunks())

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={},
            on_interrupt=None,
        )
        collected: list[Any] = []
        with pytest.raises(StreamAbortError):
            async for chunk in result:
                collected.append(chunk)
        assert collected == ["partial"]
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


# ──────────────────────────────────────────────────────────────────────────────
# Protocol boundary
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_v1_message_rejected_with_failure(redis_available, queue_name):
    """A pre-v2 message (missing `protocol` field) must terminate as a failed
    result rather than being processed. This surfaces the migration boundary
    so operators discover leftover v1 producers immediately."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    import json

    import redis.asyncio as aioredis

    controller = DummyController(workflows=[WORKFLOW_ID])
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        client = aioredis.from_url("redis://localhost:6379", decode_responses=False)
        try:
            # Simulate a v1 producer directly on the raw queue key.
            v1_message = json.dumps({
                "task_id": "task-1",
                "run_id": "run-1",
                "input": {"greeting": "hi"},
            })
            await client.lpush(f"{queue_name}:{WORKFLOW_ID}", v1_message)

            # Give the subscriber time to process; then verify it did NOT invoke
            # the controller (unsupported protocol) — either dropped or ended
            # with a failed result. We assert the controller never saw the input.
            await asyncio.sleep(0.5)
            assert controller.received_inputs == []
        finally:
            await client.aclose()
    finally:
        await _stop_subscriber(subscriber)
