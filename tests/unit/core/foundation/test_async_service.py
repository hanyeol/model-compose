"""Tests for AsyncService.run_in_thread.

The main guarantee: while a blocking callable is executed via run_in_thread,
the caller's event loop must remain free to process other coroutines. This
is what lets a component do CPU-heavy or blocking work without stalling
the whole workflow controller.

A second guarantee: cancelling the returned future propagates into the
thread's inner asyncio task at its next await, so pure-async runners unwind
cleanly (finally blocks run, resources release), nested run_in_thread calls
don't leak "Event loop is closed" errors, and no scenario deadlocks.
"""
from __future__ import annotations

import asyncio
import random
import threading
import time

import pytest

from mindor.core.foundation.async_service import AsyncService


# Wrap potentially-hanging scenarios in a timeout; a TimeoutError from any of
# these tests means a deadlock regressed, not a slow machine.
DEADLOCK_TIMEOUT = 5.0


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _StubService(AsyncService):
    """Minimal AsyncService just to expose run_in_thread."""
    def __init__(self):
        super().__init__(daemon=False)


@pytest.mark.anyio
async def test_run_in_thread_does_not_block_event_loop():
    """While a run_in_thread call sleeps synchronously for BLOCK_SECONDS,
    the main event loop should still be able to tick many times."""
    service = _StubService()

    BLOCK_SECONDS = 0.3
    TICK_INTERVAL = 0.01

    async def _blocking_work():
        # time.sleep releases the GIL, mimicking a blocking C-level call
        # (e.g. sqlite3 query, torch inference).
        time.sleep(BLOCK_SECONDS)
        return "done"

    async def _count_ticks():
        # Tick as often as possible while the blocking task runs.
        count = 0
        deadline = asyncio.get_running_loop().time() + BLOCK_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(TICK_INTERVAL)
            count += 1
        return count

    # run_in_thread returns an asyncio.Future that starts a worker thread
    # immediately; we can await it in parallel with the tick loop.
    blocking = service.run_in_thread(_blocking_work)
    ticks = await _count_ticks()
    result = await blocking

    assert result == "done"
    # We should have ticked at least half of the theoretical max — a much
    # smaller number would indicate the loop was blocked. In practice this
    # is close to BLOCK_SECONDS / TICK_INTERVAL (= 30).
    expected_min = int((BLOCK_SECONDS / TICK_INTERVAL) * 0.5)
    assert ticks >= expected_min, (
        f"Event loop appeared blocked: only {ticks} ticks in {BLOCK_SECONDS}s "
        f"(expected >= {expected_min})"
    )


@pytest.mark.anyio
async def test_run_in_thread_runs_multiple_calls_concurrently():
    """Several run_in_thread calls kicked off together should complete in
    roughly the duration of one call, not sum of all — proving they run in
    parallel threads, not serialized on the event loop."""
    service = _StubService()

    BLOCK_SECONDS = 0.2
    CALLS = 30

    async def _blocking_work():
        time.sleep(BLOCK_SECONDS)
        return time.monotonic()

    start = time.monotonic()
    finish_times = await asyncio.gather(*[
        service.run_in_thread(_blocking_work) for _ in range(CALLS)
    ])
    elapsed = time.monotonic() - start

    # Parallel: elapsed ~ BLOCK_SECONDS (plus per-thread startup overhead).
    # Serial would be BLOCK_SECONDS * CALLS = 6s. We allow generous slack
    # for thread creation cost and CI jitter, but the ratio should stay
    # far from the serialized cost.
    assert elapsed < BLOCK_SECONDS * 5, (
        f"Expected roughly parallel execution but took {elapsed:.2f}s "
        f"(would be {BLOCK_SECONDS * CALLS}s if serialized)"
    )
    assert len(finish_times) == CALLS


@pytest.mark.anyio
async def test_run_in_thread_forwards_args_and_kwargs():
    """The *args/**kwargs support added to run_in_thread should reach the
    runner intact."""
    service = _StubService()

    async def _runner(a, b, *, c):
        return (a, b, c)

    result = await service.run_in_thread(_runner, 1, 2, c=3)
    assert result == (1, 2, 3)


@pytest.mark.anyio
async def test_run_in_thread_propagates_exception():
    """Exceptions raised inside the worker should surface on the awaiter."""
    service = _StubService()

    async def _raiser():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await service.run_in_thread(_raiser)


# ---------------------------------------------------------------------------
# Cancellation semantics
#
# When the outer future is cancelled we forward the cancel into the thread's
# inner asyncio task. Pure-async runners unwind at their next await; sync
# blocking calls cannot be interrupted (documented limitation). Nothing must
# deadlock and no scenario may raise "Event loop is closed".
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cancel_delivered_into_runner():
    service = _StubService()
    inside_cancelled = False

    async def runner():
        nonlocal inside_cancelled
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            inside_cancelled = True
            raise

    fut = service.run_in_thread(runner)
    await asyncio.sleep(0.1)
    fut.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)

    # Give the inner thread a moment to record the observation.
    await asyncio.sleep(0.1)
    assert inside_cancelled
    assert fut.cancelled()


@pytest.mark.anyio
async def test_finally_runs_on_cancel():
    service = _StubService()
    hit_finally = False

    async def runner():
        nonlocal hit_finally
        try:
            await asyncio.sleep(5.0)
        finally:
            hit_finally = True

    fut = service.run_in_thread(runner)
    await asyncio.sleep(0.1)
    fut.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)

    await asyncio.sleep(0.1)
    assert hit_finally


@pytest.mark.anyio
async def test_cancel_after_completion_is_noop():
    service = _StubService()

    async def runner():
        return "done"

    fut = service.run_in_thread(runner)
    result = await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)
    fut.cancel()  # too late
    assert result == "done"
    assert fut.done() and not fut.cancelled()


@pytest.mark.anyio
async def test_nested_awaits_receive_cancel():
    service = _StubService()
    reached: list[str] = []

    async def deep():
        try:
            await asyncio.sleep(3.0)
        except asyncio.CancelledError:
            reached.append("deep")
            raise

    async def middle():
        try:
            await deep()
        except asyncio.CancelledError:
            reached.append("middle")
            raise

    async def runner():
        try:
            await middle()
        except asyncio.CancelledError:
            reached.append("runner")
            raise

    fut = service.run_in_thread(runner)
    await asyncio.sleep(0.1)
    fut.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)

    await asyncio.sleep(0.1)
    assert set(reached) == {"deep", "middle", "runner"}


@pytest.mark.anyio
async def test_outer_awaiting_task_cancel_propagates():
    service = _StubService()
    inner_saw_cancel = False

    async def runner():
        nonlocal inner_saw_cancel
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            inner_saw_cancel = True
            raise

    fut = service.run_in_thread(runner)

    async def outer():
        await fut

    outer_task = asyncio.create_task(outer())
    await asyncio.sleep(0.1)
    outer_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(outer_task, DEADLOCK_TIMEOUT)

    await asyncio.sleep(0.1)
    assert fut.cancelled()
    assert inner_saw_cancel


@pytest.mark.anyio
async def test_self_cancel_from_inside():
    service = _StubService()
    fut_ref: list[asyncio.Future | None] = [None]

    async def runner():
        await asyncio.sleep(0.05)
        fut_ref[0].cancel()
        # Next await observes the cancellation propagated back into us.
        await asyncio.sleep(1.0)
        return "should not reach"

    fut = service.run_in_thread(runner)
    fut_ref[0] = fut
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)


@pytest.mark.anyio
async def test_multiple_concurrent_cancels_are_safe():
    service = _StubService()

    async def runner():
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            raise

    fut = service.run_in_thread(runner)
    await asyncio.sleep(0.1)

    async def cancel_once():
        fut.cancel()

    await asyncio.gather(*(cancel_once() for _ in range(10)))
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)


@pytest.mark.anyio
async def test_stuck_sync_thread_does_not_block_caller():
    """A runner blocked on a sync threading.Lock cannot honour cancel — that's
    a documented limitation of running sync code in a thread. But the CALLER
    must return promptly with the future in cancelled state; other tasks
    stay responsive. Without this, workflow cancel would hang forever if the
    thread had a stuck sync call."""
    service = _StubService()
    held = threading.Lock()
    held.acquire()
    started = threading.Event()

    async def runner():
        started.set()
        try:
            held.acquire()  # blocks the thread's event loop entirely
        finally:
            if held.locked():
                held.release()

    fut = service.run_in_thread(runner)
    # Wait for the runner to enter the blocking call.
    await asyncio.get_running_loop().run_in_executor(None, started.wait, 2.0)
    fut.cancel()

    # We deliberately do NOT await `fut` — that would wait forever for the
    # stuck thread. We verify the future is in cancelled state.
    await asyncio.sleep(0.2)
    assert fut.cancelled()

    # Release the lock so the stuck thread can exit before test teardown.
    held.release()


@pytest.mark.anyio
async def test_nested_run_in_thread_completes():
    service = _StubService()

    async def inner():
        await asyncio.sleep(0.05)
        return "inner"

    async def outer():
        return await service.run_in_thread(inner)

    result = await asyncio.wait_for(service.run_in_thread(outer), DEADLOCK_TIMEOUT)
    assert result == "inner"


@pytest.mark.anyio
async def test_nested_run_in_thread_cancel_does_not_raise_loop_closed():
    """When outer cancels a 3-level nested run_in_thread, the innermost
    completion callback fires after the middle thread's loop has already
    been closed. call_soon_threadsafe would raise RuntimeError; the helper
    must swallow that specific case rather than crashing the worker."""
    service = _StubService()

    async def inner():
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            raise

    async def middle():
        return await service.run_in_thread(inner)

    async def outer():
        return await service.run_in_thread(middle)

    fut = service.run_in_thread(outer)
    await asyncio.sleep(0.1)
    fut.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)


@pytest.mark.anyio
async def test_immediate_cancel_hammer():
    """Cancel a fresh future before its worker has finished setting up the
    inner task. Repeated to shake out races between _propagate_cancel and
    _run_and_set_result."""
    service = _StubService()

    async def one():
        async def runner():
            await asyncio.sleep(1.0)

        fut = service.run_in_thread(runner)
        fut.cancel()
        with pytest.raises(asyncio.CancelledError):
            await fut

    await asyncio.wait_for(
        asyncio.gather(*(one() for _ in range(200))),
        timeout=15.0,
    )


@pytest.mark.anyio
async def test_rapid_spawn_and_cancel_churn():
    service = _StubService()

    async def runner():
        await asyncio.sleep(0.5)

    async def churn():
        for _ in range(100):
            fut = service.run_in_thread(runner)
            await asyncio.sleep(0.001)
            fut.cancel()
            with pytest.raises(asyncio.CancelledError):
                await fut

    await asyncio.wait_for(churn(), timeout=15.0)


@pytest.mark.anyio
async def test_fan_out_with_partial_cancel():
    service = _StubService()

    async def worker(index: int):
        await asyncio.sleep(random.uniform(0.1, 0.4))
        return index

    futures = [service.run_in_thread(worker, i) for i in range(30)]

    # Cancel a random third before any of them can naturally complete.
    await asyncio.sleep(0.05)
    for fut in random.sample(futures, 10):
        fut.cancel()

    results = await asyncio.wait_for(
        asyncio.gather(*futures, return_exceptions=True),
        timeout=DEADLOCK_TIMEOUT,
    )

    cancelled_count = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
    # Some cancels may lose the race to natural completion. The invariant is
    # simply that we do not deadlock and at least one cancel was observed.
    assert cancelled_count >= 1


@pytest.mark.anyio
async def test_runner_manages_background_tasks_on_cancel():
    """A runner that spawns its own background task in the thread loop must
    be able to tear it down cleanly when the outer future is cancelled."""
    service = _StubService()

    async def background():
        while True:
            await asyncio.sleep(0.05)

    async def runner():
        task = asyncio.create_task(background())
        try:
            await asyncio.sleep(5.0)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    fut = service.run_in_thread(runner)
    await asyncio.sleep(0.1)
    fut.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(fut, DEADLOCK_TIMEOUT)
