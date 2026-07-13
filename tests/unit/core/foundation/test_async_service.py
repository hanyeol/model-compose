"""Tests for AsyncService.run_in_thread.

The main guarantee: while a blocking callable is executed via run_in_thread,
the caller's event loop must remain free to process other coroutines. This
is what lets a component do CPU-heavy or blocking work without stalling
the whole workflow controller.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from mindor.core.foundation.async_service import AsyncService


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
