"""Unit tests for ``mindor.core.utils.active_counter.ActiveCounter``."""

import asyncio

import pytest

from mindor.core.utils.active_counter import ActiveCounter


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestAcquireRelease:
    def test_initial_count_is_zero(self):
        c = ActiveCounter()
        assert c.count == 0

    def test_acquire_increments(self):
        c = ActiveCounter()
        c.acquire()
        c.acquire()
        assert c.count == 2

    def test_release_decrements(self):
        c = ActiveCounter()
        c.acquire()
        c.acquire()
        c.release()
        assert c.count == 1


class TestWaitForZero:
    @pytest.mark.anyio
    async def test_returns_immediately_when_already_zero(self):
        c = ActiveCounter()
        # No raise, no hang — completes synchronously.
        await asyncio.wait_for(c.wait_for_zero(), timeout=0.1)

    @pytest.mark.anyio
    async def test_returns_when_count_drops_to_zero(self):
        c = ActiveCounter()
        c.acquire()

        async def release_soon():
            await asyncio.sleep(0.01)
            c.release()

        await asyncio.gather(c.wait_for_zero(timeout=1.0), release_soon())
        assert c.count == 0

    @pytest.mark.anyio
    async def test_timeout_raises_when_count_stays_positive(self):
        c = ActiveCounter()
        c.acquire()
        with pytest.raises(asyncio.TimeoutError):
            await c.wait_for_zero(timeout=0.02)


class TestReset:
    def test_reset_drops_count_to_zero(self):
        c = ActiveCounter()
        c.acquire()
        c.acquire()
        c.reset()
        assert c.count == 0

    @pytest.mark.anyio
    async def test_reset_releases_waiters(self):
        c = ActiveCounter()
        c.acquire()

        async def reset_soon():
            await asyncio.sleep(0.01)
            c.reset()

        await asyncio.gather(c.wait_for_zero(timeout=1.0), reset_soon())
