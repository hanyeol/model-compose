"""Unit tests for ``mindor.core.utils.work_queue.WorkQueue``.

Focus: cancellation semantics for scheduled work.

Two cases matter for correctness in the wider system (controller.task_queue,
component.work_queue):

1. Work cancelled **while queued** (worker has not popped it yet) must not run.
2. Work cancelled **while running** must cooperatively stop, and the worker
   must survive to process the next item.

Additionally we verify the pre-existing invariants — normal completion,
exception propagation, and worker isolation from handler CancelledError —
so the changes to _worker don't regress them.
"""

import asyncio

import pytest

from mindor.core.utils.work_queue import WorkQueue


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestNormalDispatch:
    @pytest.mark.anyio
    async def test_handler_result_is_delivered(self):
        async def handler(x):
            return x * 2

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            future = await q.schedule(21)
            assert await future == 42
        finally:
            await q.stop(timeout=1.0)

    @pytest.mark.anyio
    async def test_handler_exception_is_propagated(self):
        async def handler():
            raise ValueError("boom")

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            future = await q.schedule()
            with pytest.raises(ValueError, match="boom"):
                await future
        finally:
            await q.stop(timeout=1.0)


class TestCancelWhileQueued:
    @pytest.mark.anyio
    async def test_queued_item_cancelled_before_pop_does_not_run(self):
        """The single worker is busy with a slow task; a second scheduled item
        gets cancelled before the worker can pop it — the handler must never
        be invoked for that item."""
        executed = []

        async def handler(tag):
            executed.append(f"start:{tag}")
            await asyncio.sleep(0.3)
            executed.append(f"done:{tag}")
            return tag

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            slow = await q.schedule("slow")
            queued = await q.schedule("queued")

            # Give the worker a tick to pick up 'slow'.
            await asyncio.sleep(0.05)

            # 'queued' is still waiting in the asyncio.Queue at this point.
            queued.cancel()

            # Wait for 'slow' to finish and the worker to drain the queue.
            await slow
            await asyncio.sleep(0.2)

            assert executed == ["start:slow", "done:slow"]
            assert queued.cancelled()
        finally:
            await q.stop(timeout=1.0)

    @pytest.mark.anyio
    async def test_queue_drains_past_a_cancelled_item(self):
        """A cancelled item mid-queue must not block later items."""
        executed = []

        async def handler(tag):
            executed.append(tag)
            await asyncio.sleep(0.05)
            return tag

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            first = await q.schedule("first")
            middle = await q.schedule("middle")
            last = await q.schedule("last")

            # Wait a tick so the worker starts 'first', leaving middle+last queued.
            await asyncio.sleep(0.02)
            middle.cancel()

            assert await first == "first"
            assert await last == "last"
            assert middle.cancelled()

            # 'middle' was skipped entirely.
            assert executed == ["first", "last"]
        finally:
            await q.stop(timeout=1.0)


class TestCancelWhileRunning:
    @pytest.mark.anyio
    async def test_running_handler_is_cancelled_when_future_cancelled(self):
        """Cancelling the future of an in-flight handler must propagate cancel
        into the handler task — the handler observes CancelledError."""
        observed = {}

        async def handler():
            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                observed["cancelled"] = True
                raise
            observed["cancelled"] = False

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            future = await q.schedule()
            # Let the worker actually enter the handler.
            await asyncio.sleep(0.05)

            future.cancel()

            # Handler observes cancel + future settles as cancelled.
            await asyncio.sleep(0.1)
            assert observed.get("cancelled") is True
            assert future.cancelled()
        finally:
            await q.stop(timeout=1.0)

    @pytest.mark.anyio
    async def test_worker_survives_after_handler_cancel(self):
        """After cancelling an in-flight handler, the worker must still process
        subsequent scheduled work (must not exit its loop)."""
        async def handler(tag):
            if tag == "slow":
                await asyncio.sleep(5.0)
                return "slow-done"
            return f"quick-{tag}"

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            slow = await q.schedule("slow")
            await asyncio.sleep(0.05)  # worker enters slow handler
            slow.cancel()

            # Give the cancel time to propagate.
            await asyncio.sleep(0.05)
            assert slow.cancelled()

            # Now schedule a fresh task — the worker must pick it up.
            follow_up = await q.schedule("A")
            result = await asyncio.wait_for(follow_up, timeout=1.0)
            assert result == "quick-A"
        finally:
            await q.stop(timeout=1.0)

    @pytest.mark.anyio
    async def test_handler_raising_cancelled_error_does_not_kill_worker(self):
        """Pre-existing invariant: a handler that raises CancelledError from
        within itself (e.g. cooperative shutdown) must not cancel the worker."""
        async def handler(tag):
            if tag == "self-cancel":
                raise asyncio.CancelledError()
            return tag

        q = WorkQueue(max_concurrent_count=1, handler=handler)
        await q.start()
        try:
            f1 = await q.schedule("self-cancel")
            f2 = await q.schedule("after")

            # f1 completes as cancelled (worker translates handler cancel to future cancel).
            await asyncio.sleep(0.05)
            assert f1.cancelled()

            # Worker survived and processed f2.
            assert await asyncio.wait_for(f2, timeout=1.0) == "after"
        finally:
            await q.stop(timeout=1.0)
