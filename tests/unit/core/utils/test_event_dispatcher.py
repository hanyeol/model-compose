"""Unit tests for ``mindor.core.utils.event_dispatcher.EventDispatcher``.

The dispatcher exists to fix an ordering bug: previously each event was
fanned out via ``asyncio.create_task``, so two events with awaits inside
their handlers could complete out of order. These tests pin down:

1. Same-key FIFO ordering (the main regression to prevent).
2. Different keys run concurrently (no head-of-line blocking across
   subscribers).
3. Exceptions in a handler don't stop the worker.
4. ``close()`` drains pending work and stops workers.
5. Dispatches after ``close()`` are dropped.
6. ``unregister()`` drains a single subscriber's queue.
7. ``close(timeout=...)`` cancels workers that don't finish in time.
"""

import asyncio

import pytest

from mindor.core.utils.event_dispatcher import EventDispatcher


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestOrdering:
    @pytest.mark.anyio
    async def test_same_key_runs_in_fifo_order_even_when_earlier_handlers_are_slower(self):
        """Same-key events must complete in dispatch order regardless of handler duration."""
        results = []

        async def handler(i, delay):
            await asyncio.sleep(delay)
            results.append(i)

        d = EventDispatcher()
        try:
            # Descending delays: without serialization, results would arrive as [3, 2, 1].
            d.dispatch("k", lambda: handler(1, 0.05))
            d.dispatch("k", lambda: handler(2, 0.02))
            d.dispatch("k", lambda: handler(3, 0.01))
            await d.close(timeout=2)
        finally:
            await d.close(timeout=1)

        assert results == [1, 2, 3]

    @pytest.mark.anyio
    async def test_different_keys_run_concurrently(self):
        """Independent keys must not block each other."""
        started = asyncio.Event()

        async def slow():
            started.set()
            await asyncio.sleep(0.5)

        async def fast():
            await started.wait()  # only completes if `slow` was actually running in parallel

        d = EventDispatcher()
        try:
            d.dispatch("slow", lambda: slow())
            d.dispatch("fast", lambda: fast())
            # If serialized, fast() would wait 0.5s. With concurrency, it wakes as soon
            # as slow() sets `started`, well under the timeout.
            await asyncio.wait_for(d.close(timeout=2), timeout=1.5)
        finally:
            await d.close(timeout=1)


class TestErrorIsolation:
    @pytest.mark.anyio
    async def test_handler_exception_does_not_stop_worker(self):
        results = []

        async def bad():
            raise RuntimeError("boom")

        async def good(i):
            results.append(i)

        d = EventDispatcher()
        try:
            d.dispatch("k", lambda: bad())
            d.dispatch("k", lambda: good(1))
            d.dispatch("k", lambda: good(2))
            await d.close(timeout=2)
        finally:
            await d.close(timeout=1)

        assert results == [1, 2]


class TestLifecycle:
    @pytest.mark.anyio
    async def test_close_drains_pending_handlers(self):
        results = []

        async def handler(i):
            await asyncio.sleep(0.01)
            results.append(i)

        d = EventDispatcher()
        for i in range(5):
            d.dispatch("k", lambda i=i: handler(i))

        await d.close(timeout=2)

        assert results == [0, 1, 2, 3, 4]

    @pytest.mark.anyio
    async def test_dispatch_after_close_is_ignored(self):
        results = []

        async def handler():
            results.append("ran")

        d = EventDispatcher()
        await d.close(timeout=1)

        d.dispatch("k", lambda: handler())
        # Give any (hypothetical) worker time to run.
        await asyncio.sleep(0.05)

        assert results == []

    @pytest.mark.anyio
    async def test_close_with_no_subscribers_is_noop(self):
        d = EventDispatcher()
        await d.close(timeout=0.1)  # must not raise

    @pytest.mark.anyio
    async def test_unregister_drops_key_but_pending_handlers_still_run(self):
        """unregister() removes the key from the map immediately but the worker
        drains any already-queued handlers before exiting (via the sentinel)."""
        results = []

        async def handler(i):
            await asyncio.sleep(0.01)
            results.append(i)

        d = EventDispatcher()
        try:
            d.dispatch("k", lambda: handler(1))
            d.dispatch("k", lambda: handler(2))
            # Grab the worker task before unregister() drops the reference so
            # we can await its shutdown.
            worker = d._workers["k"]
            d.unregister("k")

            assert "k" not in d._queues
            assert "k" not in d._workers

            await asyncio.wait_for(worker, timeout=1)
            assert results == [1, 2]
        finally:
            await d.close(timeout=1)

    @pytest.mark.anyio
    async def test_close_timeout_cancels_hung_worker(self):
        started = asyncio.Event()

        async def hang():
            started.set()
            await asyncio.sleep(60)  # would exceed the test timeout

        d = EventDispatcher()
        d.dispatch("k", lambda: hang())
        await started.wait()

        # close() should return within timeout even though the handler is stuck.
        await asyncio.wait_for(d.close(timeout=0.1), timeout=1)
