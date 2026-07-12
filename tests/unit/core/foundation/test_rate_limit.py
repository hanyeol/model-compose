"""Tests for RateLimiter: token bucket, min-interval, and combined gates."""

import asyncio
import time

import pytest

from mindor.core.foundation.rate_limit import RateLimiter
from mindor.dsl.schema.common.rate_limit import RateLimitConfig


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


async def _measure(coro):
    start = time.monotonic()
    await coro
    return time.monotonic() - start


class TestTokenBucket:

    @pytest.mark.anyio
    async def test_initial_burst_passes_immediately(self):
        limiter = RateLimiter(RateLimitConfig(requests=5, period="1s"))
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    @pytest.mark.anyio
    async def test_throttles_after_capacity_exhausted(self):
        limiter = RateLimiter(RateLimitConfig(requests=4, period="0.4s"))
        # First 4 should be immediate; the 5th must wait roughly 0.1s (one refill).
        for _ in range(4):
            await limiter.acquire()
        elapsed = await _measure(limiter.acquire())
        assert elapsed >= 0.08
        assert elapsed < 0.25

    @pytest.mark.anyio
    async def test_request_count_within_window(self):
        # 10 acquires with a 5/0.2s budget must take at least (10 - capacity) * (0.2/5) seconds.
        limiter = RateLimiter(RateLimitConfig(requests=5, period="0.2s"))
        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        # capacity=5 immediate, 5 more at 0.04s spacing → ~0.2s
        assert elapsed >= 0.18
        assert elapsed < 0.5

    @pytest.mark.anyio
    async def test_negative_token_reservation_monotonic(self):
        """When capacity+N coroutines acquire concurrently, completions must
        spread out monotonically by the refill rate. If lock-held sleep
        occurred, completions would serialize and pile up instead."""
        capacity = 3
        extra = 5
        period_seconds = 0.3
        limiter = RateLimiter(RateLimitConfig(requests=capacity, period=f"{period_seconds}s"))
        refill_rate = capacity / period_seconds  # tokens per sec
        gap = 1 / refill_rate

        completions = []

        async def worker():
            await limiter.acquire()
            completions.append(time.monotonic())

        start = time.monotonic()
        await asyncio.gather(*[worker() for _ in range(capacity + extra)])

        # The first `capacity` completions are immediate; subsequent ones
        # must arrive separated by roughly `gap` seconds.
        completions.sort()
        for i in range(capacity, len(completions)):
            expected_offset = (i - capacity + 1) * gap
            actual_offset = completions[i] - start
            # Allow generous slack for event-loop jitter, but reject piling up.
            assert actual_offset >= expected_offset * 0.8
            assert actual_offset < expected_offset + gap + 0.1

    @pytest.mark.anyio
    async def test_burst_larger_than_requests(self):
        limiter = RateLimiter(RateLimitConfig(requests=2, period="0.2s", burst=5))
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05  # all 5 fit in initial burst


class TestMinInterval:

    @pytest.mark.anyio
    async def test_enforces_spacing(self):
        limiter = RateLimiter(RateLimitConfig(interval="50ms"))
        timestamps = []
        for _ in range(4):
            await limiter.acquire()
            timestamps.append(time.monotonic())

        for prev, curr in zip(timestamps, timestamps[1:]):
            assert curr - prev >= 0.045  # 50ms with small slack

    @pytest.mark.anyio
    async def test_first_acquire_immediate(self):
        limiter = RateLimiter(RateLimitConfig(interval="100ms"))
        elapsed = await _measure(limiter.acquire())
        assert elapsed < 0.01


class TestCombined:

    @pytest.mark.anyio
    async def test_both_constraints_satisfied(self):
        # Token bucket allows 10/s (~100ms cadence on average) but min-interval is
        # 150ms, so min-interval should dominate after the initial burst.
        limiter = RateLimiter(RateLimitConfig(requests=10, period="1s", interval="150ms"))

        # Burn the burst.
        for _ in range(10):
            await limiter.acquire()

        timestamps = []
        for _ in range(3):
            await limiter.acquire()
            timestamps.append(time.monotonic())

        for prev, curr in zip(timestamps, timestamps[1:]):
            assert curr - prev >= 0.14  # ~150ms with slack

    @pytest.mark.anyio
    async def test_interval_does_not_stack_on_token_wait(self):
        """min-interval should chain off the bucket's send-at time, not add to
        raw now(). With token-wait (~100ms) > interval (50ms), the third
        acquire should wait ~100ms, not ~150ms (naive sum)."""
        limiter = RateLimiter(RateLimitConfig(requests=2, period="0.2s", interval="50ms"))

        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        # Burst of 2 is immediate; 3rd needs token refill (~0.1s). If interval
        # naively stacked, elapsed would be ~0.15s+.
        assert elapsed < 0.14
