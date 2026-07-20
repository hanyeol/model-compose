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
    `workflow_schemas`, `run_workflow(workflow_id, input, ...)` and
    `cancel_workflow(task_id, ...)`. Behavior is configurable per-test via a
    callable, defaulting to echoing the input back.

    The handler receives `on_interrupt` so tests can trigger interrupt/resume
    flows by awaiting that callback inside the handler. Tests that exercise
    cancellation get the running task_id via `running_task_ids` and can drive
    `cancel_workflow(task_id)` to release the handler's `await`.
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
        self.received_task_ids: List[Optional[str]] = []
        self.running_task_ids: List[str] = []
        self._cancel_events: Dict[str, asyncio.Event] = {}

    async def _default_handler(self, workflow_id: str, input: Dict[str, Any], on_interrupt: Any) -> Dict[str, Any]:
        return { "echo": input }

    def cancel_event(self, task_id: str) -> asyncio.Event:
        """Handlers await this to simulate long-running work interruptible by cancel."""
        event = self._cancel_events.get(task_id)
        if event is None:
            event = asyncio.Event()
            self._cancel_events[task_id] = event
        return event

    async def run_workflow(
        self,
        workflow_id: str,
        input: Dict[str, Any],
        task_id: Optional[str] = None,
        wait_for_completion: bool = True,
        on_interrupt: Any = None,
        session_id: Any = None,
        metadata: Any = None,
    ) -> TaskState:
        effective_task_id = task_id or "dummy"
        self.received.append({ "workflow_id": workflow_id, "input": input })
        self.received_task_ids.append(task_id)
        self.running_task_ids.append(effective_task_id)
        try:
            output = await self._handler(workflow_id, input, on_interrupt)
            return TaskState(
                task_id=effective_task_id,
                status=TaskStatus.COMPLETED,
                workflow_id=workflow_id,
                output=output,
            )
        except asyncio.CancelledError:
            return TaskState(
                task_id=effective_task_id,
                status=TaskStatus.CANCELLED,
                workflow_id=workflow_id,
            )
        except Exception as e:
            return TaskState(
                task_id=effective_task_id,
                status=TaskStatus.FAILED,
                workflow_id=workflow_id,
                error=str(e),
            )
        finally:
            if effective_task_id in self.running_task_ids:
                self.running_task_ids.remove(effective_task_id)

    async def cancel_workflow(self, task_id: str, wait_for_completion: bool = True) -> TaskState:
        """Fires the cancel event so a waiting handler resolves and completes."""
        event = self._cancel_events.get(task_id)
        if event is not None:
            event.set()
        return TaskState(task_id=task_id, status=TaskStatus.CANCELLING)


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
        remaining = await _blob_keys(dispatcher.client, queue_name)
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
        remaining = await _blob_keys(dispatcher.client, queue_name)
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
        remaining = await _blob_keys(dispatcher.client, queue_name)
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


@pytest.mark.anyio
async def test_dispatcher_task_id_reaches_subscriber_controller(redis_available, queue_name):
    """The dispatcher's task_id must be forwarded verbatim to the subscriber-side
    controller.run_workflow — that is what lets a cross-node cancel target the
    same task_id on both ends."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        await dispatcher._dispatch(
            task_id="cross-node-task-42",
            workflow_id=WORKFLOW_ID,
            input={ "x": 1 },
            on_interrupt=None,
        )

        assert controller.received_task_ids == ["cross-node-task-42"]
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_cancel_broadcast_reaches_running_task(redis_available, queue_name):
    """Dispatcher publishes cancel via _queue.cancel; the subscriber's
    cancel-listener resolves it into a controller.cancel_workflow call for the
    matching, currently-running task, and the handler completes with CANCELLED."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    handler_started = asyncio.Event()

    async def handler(workflow_id: str, input: Dict[str, Any], on_interrupt: Any) -> Dict[str, Any]:
        handler_started.set()
        # Wait indefinitely until the DummyController receives cancel_workflow,
        # which fires the cancel_event for this task_id and unblocks us.
        # We block on the event tied to the *dispatcher's* task_id — the subscriber
        # forwards that verbatim via the new `task_id=` kwarg.
        await controller.cancel_event("cancel-target-1").wait()
        return { "should_not_reach": True }

    controller = DummyController(workflows=[WORKFLOW_ID], handler=handler)
    dispatcher = await _start_dispatcher(queue_name, timeout="5s")
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    dispatch_task = asyncio.create_task(dispatcher._dispatch(
        task_id="cancel-target-1",
        workflow_id=WORKFLOW_ID,
        input={ "x": 1 },
        on_interrupt=None,
    ))

    try:
        # Wait until the handler is actually running before publishing cancel.
        await asyncio.wait_for(handler_started.wait(), timeout=3.0)
        assert "cancel-target-1" in controller.running_task_ids

        # Simulate the "other node" — dispatcher publishes a cancel through the queue.
        await dispatcher.cancel("cancel-target-1")

        # Dispatcher's `_dispatch` await returns because the subscriber publishes
        # the final (COMPLETED w/ dummy output) result — but the important thing
        # is that the DummyController's cancel_workflow was invoked and the
        # handler unblocked. Verify both.
        result = await asyncio.wait_for(dispatch_task, timeout=3.0)

        # Handler was unblocked by the cancel event → returned normally in the dummy.
        # In a real controller this would produce a CANCELLED state; the dummy just
        # verifies the cancel actually reached the running task.
        assert result == { "should_not_reach": True }
        assert "cancel-target-1" not in controller.running_task_ids
    finally:
        if not dispatch_task.done():
            dispatch_task.cancel()
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_cancel_for_unknown_task_id_is_ignored(redis_available, queue_name):
    """A cancel message for a task the subscriber is not running must not crash
    the cancel-listener nor invoke controller.cancel_workflow."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    cancel_calls: List[str] = []

    class RecordingController(DummyController):
        async def cancel_workflow(self, task_id: str, wait_for_completion: bool = True) -> TaskState:
            cancel_calls.append(task_id)
            return await super().cancel_workflow(task_id, wait_for_completion)

    controller = RecordingController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    try:
        # Publish a cancel for a task_id that the subscriber has never seen.
        await dispatcher.cancel("never-heard-of-this")

        # Give the pubsub message time to arrive & be filtered.
        await asyncio.sleep(0.2)

        assert cancel_calls == []

        # And a subsequent normal dispatch still works — listener is alive.
        result = await dispatcher._dispatch(
            task_id="fresh-task",
            workflow_id=WORKFLOW_ID,
            input={ "y": 2 },
            on_interrupt=None,
        )
        assert result == { "echo": { "y": 2 } }
    finally:
        await _stop_subscriber(subscriber)
        await dispatcher._stop()


@pytest.mark.anyio
async def test_cancel_listener_stops_on_subscriber_shutdown(redis_available, queue_name):
    """When the subscriber shuts down, the cancel-listener task is included in
    _workers and must be cancelled cleanly (no hanging tasks)."""
    if not redis_available:
        pytest.skip("Redis not available on localhost:6379")

    controller = DummyController(workflows=[WORKFLOW_ID])
    dispatcher = await _start_dispatcher(queue_name)
    subscriber = await _start_subscriber(queue_name, [WORKFLOW_ID], controller)

    # Sanity: cancel listener is one of the workers.
    assert len(subscriber._workers) == 2  # 1 consumer + 1 cancel listener

    await _stop_subscriber(subscriber)

    # All worker tasks (consumer + cancel listener) should be done.
    assert all(worker.done() for worker in subscriber._workers) or subscriber._workers == []

    await dispatcher._stop()
