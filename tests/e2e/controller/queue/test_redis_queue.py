"""End-to-end tests for Redis queue dispatcher + subscriber.

Brings up a real RedisControllerQueueService and RedisCommonQueueSubscriberControllerAdapterService
side-by-side against a real Redis (localhost:6379 by default). Each test isolates
itself via a unique queue name so parallel runs do not collide.

Tests are skipped automatically if Redis is unreachable.
"""

import asyncio
import io
from typing import Any, Awaitable, Callable, Dict, List, Optional

import pytest

from starlette.datastructures import UploadFile

from mindor.core.controller.base import InterruptState, TaskState, TaskStatus
from mindor.core.controller.adapters.services.queue_subscriber.drivers.redis import (
    RedisCommonQueueSubscriberControllerAdapterService,
)
from mindor.core.controller.queue.drivers.redis import RedisControllerQueueService
from mindor.dsl.schema.controller import (
    ControllerAdapterType,
    ControllerQueueDriver,
    QueueSubscriberDriver,
    RedisControllerQueueConfig,
    RedisQueueSubscriberControllerAdapterConfig,
)


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
    """Unique queue name per test to isolate keys in shared Redis."""
    import ulid
    return f"test-e2e-{request.node.name}-{ulid.ulid()}"


# ──────────────────────────────────────────────────────────────────────────────
# Dummy controller — echoes input back as TaskState output
# ──────────────────────────────────────────────────────────────────────────────

class DummyController:
    """Minimal ControllerService stand-in for the subscriber.

    Implements only what RedisCommonQueueSubscriberControllerAdapterService touches:
    `workflow_schemas` and `run_workflow(workflow_id, input, ...)`. Behavior is
    configurable per-test via a callable, defaulting to echoing the input back.

    The handler receives `on_interrupt` so tests can trigger interrupt/resume
    flows by awaiting that callback inside the handler.
    """

    def __init__(
        self,
        workflows: List[str],
        handler: Optional[Callable[[str, Dict[str, Any], Any], Awaitable[Dict[str, Any]]]] = None,
    ):
        # subscriber falls back to workflow_schemas.keys() when config.workflows is None
        self.workflow_schemas = { wf: None for wf in workflows }
        self._handler = handler or self._default_handler
        self.received: List[Dict[str, Any]] = []

    async def _default_handler(self, workflow_id: str, input: Dict[str, Any], on_interrupt: Any) -> Dict[str, Any]:
        return { "echo": input }

    async def run_workflow(
        self,
        workflow_id: str,
        input: Dict[str, Any],
        wait_for_completion: bool = True,
        on_interrupt: Any = None,
        session_id: Any = None,
        metadata: Any = None,
    ) -> TaskState:
        self.received.append({ "workflow_id": workflow_id, "input": input })
        try:
            output = await self._handler(workflow_id, input, on_interrupt)
            return TaskState(
                task_id="dummy",
                status=TaskStatus.COMPLETED,
                workflow_id=workflow_id,
                output=output,
            )
        except Exception as e:
            return TaskState(
                task_id="dummy",
                status=TaskStatus.FAILED,
                workflow_id=workflow_id,
                error=str(e),
            )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers to wire up dispatcher + subscriber against a unique queue name
# ──────────────────────────────────────────────────────────────────────────────

async def _start_dispatcher(queue_name: str, **overrides) -> RedisControllerQueueService:
    config = RedisControllerQueueConfig(
        driver=ControllerQueueDriver.REDIS,
        name=queue_name,
        timeout=overrides.pop("timeout", "10s"),
        max_blob_size=overrides.pop("max_blob_size", "50M"),
        blob_ttl=overrides.pop("blob_ttl", None),
        **overrides,
    )
    service = RedisControllerQueueService(config)
    await service._start()
    return service


async def _start_subscriber(
    queue_name: str,
    workflows: List[str],
    controller: DummyController,
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
    # _serve is the actual run loop; spin it up as a background task
    serve_task = asyncio.create_task(service._serve())
    # Give the consumer loop a moment to subscribe before dispatching
    await asyncio.sleep(0.1)
    service._serve_task = serve_task  # type: ignore[attr-defined]
    return service


async def _stop_subscriber(service: RedisCommonQueueSubscriberControllerAdapterService) -> None:
    await service._shutdown()
    serve_task = getattr(service, "_serve_task", None)
    if serve_task is not None:
        try:
            await asyncio.wait_for(serve_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass


async def _blob_keys(client, queue_name: str) -> List[bytes]:
    """List all blob keys under the given queue namespace."""
    pattern = f"{queue_name}:*:blob:*".encode("utf-8")
    return [k async for k in client.scan_iter(match=pattern)]


# ──────────────────────────────────────────────────────────────────────────────
# Scenarios
# ──────────────────────────────────────────────────────────────────────────────

WORKFLOW_ID = "wf-echo"


@pytest.mark.anyio
async def test_json_input_round_trip(redis_available, queue_name):
    """A plain JSON input flows dispatcher → queue → subscriber → result."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-1",
            workflow_id=WORKFLOW_ID,
            input={ "greeting": "hi", "n": 42 },
            on_interrupt=None,
        )

        assert result == { "echo": { "greeting": "hi", "n": 42 } }
        assert controller.received == [
            { "workflow_id": WORKFLOW_ID, "input": { "greeting": "hi", "n": 42 } }
        ]
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_upload_file_round_trip(redis_available, queue_name):
    """UploadFile input is serialized into a blob and restored as UploadFile."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    payload = b"\x89PNG\r\n\x1a\n" + b"binary-image-bytes" * 100
    captured: Dict[str, Any] = {}

    async def handler(workflow_id: str, input: Dict[str, Any], on_interrupt: Any) -> Dict[str, Any]:
        image = input["image"]
        assert isinstance(image, UploadFile)
        data = await image.read()
        captured["bytes"] = data
        captured["filename"] = image.filename
        captured["content_type"] = image.content_type
        return { "size": len(data) }

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        upload = UploadFile(
            file=io.BytesIO(payload),
            filename="picture.png",
            headers={ "content-type": "image/png" },  # type: ignore[arg-type]
        )

        result = await dispatcher._dispatch(
            task_id="task-2",
            workflow_id=WORKFLOW_ID,
            input={ "image": upload, "caption": "hello" },
            on_interrupt=None,
        )

        assert result == { "size": len(payload) }
        assert captured["bytes"] == payload
        assert captured["filename"] == "picture.png"
        assert captured["content_type"] == "image/png"
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_bytes_input_round_trip(redis_available, queue_name):
    """Raw bytes input is restored as UploadFile (normalized at queue boundary)."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    payload = b"raw-bytes-payload" * 50
    captured: Dict[str, Any] = {}

    async def handler(workflow_id: str, input: Dict[str, Any], on_interrupt: Any) -> Dict[str, Any]:
        blob = input["blob"]
        assert isinstance(blob, UploadFile)
        data = await blob.read()
        captured["bytes"] = data
        return { "ok": True }

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-3",
            workflow_id=WORKFLOW_ID,
            input={ "blob": payload },
            on_interrupt=None,
        )

        assert result == { "ok": True }
        assert captured["bytes"] == payload
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_blob_cleanup_after_normal_dispatch(redis_available, queue_name):
    """After successful dispatch, no blob keys should remain under the queue namespace."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        await dispatcher._dispatch(
            task_id="task-4",
            workflow_id=WORKFLOW_ID,
            input={ "image": b"some-binary-blob" * 100 },
            on_interrupt=None,
        )

        # Subscriber consumed the blob via GETDEL — should be gone immediately.
        remaining = await _blob_keys(dispatcher._client, queue_name)
        assert remaining == []
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_dispatcher_cleanup_on_serialize_failure(redis_available, queue_name):
    """When serialize_input fails (e.g. max_blob_size exceeded), dispatcher must
    cleanup any blob keys it already wrote — nothing should leak to Redis."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    # No subscriber needed — failure happens before lpush.
    dispatcher = await _start_dispatcher(queue_name, max_blob_size="100B")

    try:
        big_payload = b"x" * 500  # Exceeds 100B limit

        with pytest.raises(Exception):
            # Should raise BlobTooLargeError (or wrapped equivalent)
            await dispatcher._dispatch(
                task_id="task-5",
                workflow_id=WORKFLOW_ID,
                input={ "huge": big_payload },
                on_interrupt=None,
            )

        # No blob keys should be lingering in Redis.
        remaining = await _blob_keys(dispatcher._client, queue_name)
        assert remaining == []
    finally:
        await dispatcher._stop()


@pytest.mark.anyio
async def test_dispatch_timeout_when_subscriber_absent(redis_available, queue_name):
    """No subscriber running — dispatcher should time out per queue.timeout."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    dispatcher = await _start_dispatcher(queue_name, timeout="500ms")

    try:
        with pytest.raises(TimeoutError, match="Queue dispatch timed out"):
            await dispatcher._dispatch(
                task_id="task-6",
                workflow_id=WORKFLOW_ID,
                input={ "x": 1 },
                on_interrupt=None,
            )

        # blob_ttl defaults to 3600s, so the (binary-less) message-only dispatch
        # leaves no blob keys; just verify cleanly.
        remaining = await _blob_keys(dispatcher._client, queue_name)
        assert remaining == []
    finally:
        await dispatcher._stop()


@pytest.mark.anyio
async def test_interrupt_resume_round_trip(redis_available, queue_name):
    """A workflow interrupts mid-execution, dispatcher answers, workflow resumes."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    received_by_dispatcher: List[Dict[str, Any]] = []

    async def dispatcher_on_interrupt(interrupt: Dict[str, Any]) -> Any:
        # subscriber serialized state.interrupt into this dict in _get_task_output
        received_by_dispatcher.append(interrupt)
        return { "decision": "approve", "echoed_message": interrupt.get("message") }

    async def handler(workflow_id: str, input: Dict[str, Any], on_interrupt: Any) -> Dict[str, Any]:
        answer = await on_interrupt(InterruptState(
            job_id="job-A",
            phase="before",
            message="please approve",
            metadata={ "step": 1 },
        ))
        return { "resumed_with": answer, "input": input }

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        result = await dispatcher._dispatch(
            task_id="task-7",
            workflow_id=WORKFLOW_ID,
            input={ "n": 1 },
            on_interrupt=dispatcher_on_interrupt,
        )

        # Dispatcher's interrupt callback was invoked with subscriber-side interrupt data
        assert len(received_by_dispatcher) == 1
        assert received_by_dispatcher[0]["job_id"] == "job-A"
        assert received_by_dispatcher[0]["phase"] == "before"
        assert received_by_dispatcher[0]["message"] == "please approve"
        assert received_by_dispatcher[0]["metadata"] == { "step": 1 }

        # Workflow resumed with dispatcher's answer and produced final output
        assert result == {
            "resumed_with": { "decision": "approve", "echoed_message": "please approve" },
            "input": { "n": 1 },
        }
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()
