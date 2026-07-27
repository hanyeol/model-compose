"""Shared test helpers for validating the async-refactor across component services.

Two concerns are covered:

- Non-blocking assertion: `assert_does_not_block(coro)` runs a coroutine
  alongside a fast `asyncio.sleep(...)` ticker and confirms the ticker keeps
  advancing. If the coroutine synchronously blocks the event loop (e.g. by
  calling into a CPU-heavy sync function without offloading), the ticker
  advances only a handful of times and the assertion fails. Use for functions
  that do CPU-bound work but are expected to yield control via
  `asyncio.to_thread` / `_run_in_executor`.

- Contract helpers: build a minimally-populated `ComponentActionContext` so
  Action.run() can be driven from a unit test without spinning up a whole
  workflow. Sources registered via `context.register_source` remain accessible
  through `${result}` interpolation exactly as in production.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from mindor.core.component.context import ComponentActionContext


T = TypeVar("T")


async def assert_does_not_block(
    coro: Awaitable[T],
    *,
    tick_interval_s: float = 0.01,
    min_ticks: int = 5,
    max_wall_s: float = 30.0,
) -> T:
    """Run `coro` concurrently with an `asyncio.sleep` ticker; assert the ticker keeps advancing.

    If the coroutine holds the event loop synchronously for its whole duration,
    the ticker will fire only once (or not at all) instead of the expected
    ``ceil(duration_s / tick_interval_s)`` times. Requiring at least ``min_ticks``
    ticks catches the case where the CPU work was NOT offloaded.

    For very fast coroutines (<50ms) this check is not meaningful and is skipped
    with a soft-pass; callers wanting to verify offloading of tiny CPU work
    should artificially slow the work (e.g. large payload) so the wall time
    dominates the tick interval.

    Returns whatever the coroutine returned so tests can also assert on results.
    """
    tick_count = 0
    stop = asyncio.Event()

    async def _ticker() -> None:
        nonlocal tick_count
        while not stop.is_set():
            await asyncio.sleep(tick_interval_s)
            tick_count += 1

    ticker_task = asyncio.create_task(_ticker())
    start = time.monotonic()

    try:
        result = await asyncio.wait_for(coro, timeout=max_wall_s)
    finally:
        stop.set()
        try:
            await asyncio.wait_for(ticker_task, timeout=1.0)
        except asyncio.TimeoutError:
            ticker_task.cancel()

    duration = time.monotonic() - start

    # If the work finished faster than a few tick intervals, we can't meaningfully
    # measure blocking. Just return the result and let the caller decide.
    if duration < tick_interval_s * min_ticks:
        return result

    expected_ticks = int(duration / tick_interval_s)
    minimum_expected = max(min_ticks, expected_ticks // 3)

    assert tick_count >= minimum_expected, (
        f"Event loop appears to have been blocked: ticker fired only "
        f"{tick_count} times in {duration:.2f}s "
        f"(expected at least {minimum_expected} ticks at {tick_interval_s}s each). "
        f"Coroutine is likely doing CPU-bound work without offloading."
    )

    return result


def make_action_context(
    input: Optional[Dict[str, Any]] = None,
    *,
    run_id: str = "test-run",
    component_id: str = "test-component",
    component_type: str = "test",
    job_id: str = "test-job",
    sources: Optional[Dict[str, Any]] = None,
) -> ComponentActionContext:
    """Build a `ComponentActionContext` suitable for driving Action.run() in tests.

    `sources` is a dict of pre-registered global sources (name -> value); the
    typical use is `{"result": {...}}` so the config's `output: ${result.field}`
    template resolves against a fixed value.
    """
    context = ComponentActionContext(
        run_id=run_id,
        input=input or {},
        workflow=None,
        component_id=component_id,
        component_type=component_type,
        job_id=job_id,
    )

    if sources:
        for key, value in sources.items():
            context.register_source(key, value)

    return context


async def collect_async(iterator) -> list:
    """Collect an async iterator into a list."""
    return [item async for item in iterator]


class BlockingWork:
    """Callable that blocks the current thread for `duration_s` seconds.

    Use inside test doubles that mimic sync CPU work, so the "does not block"
    ticker has enough wall time to accumulate ticks.
    """

    def __init__(self, duration_s: float, return_value: Any = None):
        self.duration_s = duration_s
        self.return_value = return_value
        self.call_count = 0

    def __call__(self, *args, **kwargs) -> Any:
        self.call_count += 1
        time.sleep(self.duration_s)
        return self.return_value
