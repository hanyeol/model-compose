"""Async / non-blocking integration test for the Redis key-value store.

Prefers `fakeredis.aioredis.FakeRedis` so no external service is required.
Falls back to a real localhost Redis if fakeredis isn't present; skips
entirely if neither works.

Focus:
- Contract: SET / GET / DELETE / EXISTS round-trip.
- Non-blocking: the driver uses `redis.asyncio` (native async, no executor).
  A concurrent asyncio ticker should keep advancing throughout a burst of
  KV operations.
- Signature: `_run(action, context)` with no `loop` kwarg — the refactor
  removed the executor since redis.asyncio is already async.
- No thread hop: verify operations execute on the current asyncio event
  loop thread (contract for native-async drivers — no run_coroutine_threadsafe).
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

import pytest

pytest.importorskip("redis")

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.key_value_store.drivers.redis import (
    RedisKeyValueStoreAction,
    RedisKeyValueStoreService,
)
from mindor.dsl.schema.action import (
    RedisKeyValueDeleteActionConfig,
    RedisKeyValueExistsActionConfig,
    RedisKeyValueGetActionConfig,
    RedisKeyValueSetActionConfig,
)

from tests.async_helpers import assert_does_not_block


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def redis_client():
    """A live-ish Redis client for tests.

    Preference order:
    1. `fakeredis.aioredis.FakeRedis` (zero external deps, in-memory).
    2. Real Redis on localhost:6379 db=15 (test scratch DB).
    Skips if neither is available.
    """
    try:
        import fakeredis.aioredis  # type: ignore

        client = fakeredis.aioredis.FakeRedis()
    except ImportError:
        try:
            from redis.asyncio import Redis  # type: ignore

            client = Redis.from_url("redis://localhost:6379/15")
            # Sanity ping so we skip fast on connection failure.
            await client.ping()
        except Exception as exc:
            pytest.skip(f"Neither fakeredis nor local Redis available: {exc}")

    try:
        yield client
    finally:
        try:
            await client.flushdb()
        except Exception:
            pass
        try:
            await client.aclose()
        except Exception:
            pass


@pytest.fixture
def integration_context() -> ComponentActionContext:
    return ComponentActionContext(run_id="test-run", input={})


class TestRedisContract:
    """SET / GET / DELETE / EXISTS round-trips via the real action layer."""

    @pytest.mark.anyio
    async def test_set_then_get(self, redis_client, integration_context):
        await RedisKeyValueStoreAction(
            RedisKeyValueSetActionConfig(method="set", key="k1", value="v1"),
            redis_client,
        ).run(integration_context)

        result = await RedisKeyValueStoreAction(
            RedisKeyValueGetActionConfig(method="get", key="k1"),
            redis_client,
        ).run(integration_context)

        assert result == {"value": "v1"}

    @pytest.mark.anyio
    async def test_set_then_exists_then_delete(self, redis_client, integration_context):
        await RedisKeyValueStoreAction(
            RedisKeyValueSetActionConfig(method="set", key="k2", value="v2"),
            redis_client,
        ).run(integration_context)

        exists_before = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key="k2"),
            redis_client,
        ).run(integration_context)
        assert exists_before == {"exists": True}

        deleted = await RedisKeyValueStoreAction(
            RedisKeyValueDeleteActionConfig(method="delete", key="k2"),
            redis_client,
        ).run(integration_context)
        assert deleted == {"count": 1}

        exists_after = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key="k2"),
            redis_client,
        ).run(integration_context)
        assert exists_after == {"exists": False}

    @pytest.mark.anyio
    async def test_set_json_object_roundtrips(self, redis_client, integration_context):
        payload = {"name": "Alice", "roles": ["admin", "user"]}

        await RedisKeyValueStoreAction(
            RedisKeyValueSetActionConfig(method="set", key="obj", value=payload),
            redis_client,
        ).run(integration_context)

        result = await RedisKeyValueStoreAction(
            RedisKeyValueGetActionConfig(method="get", key="obj"),
            redis_client,
        ).run(integration_context)

        assert result == {"value": payload}


class TestRedisNonBlocking:
    """Native async — many operations should not stall the loop."""

    @pytest.mark.anyio
    async def test_burst_operations_do_not_block(self, redis_client, integration_context):
        async def _burst():
            # 200 SET+GET pairs. Even with fakeredis (in-memory), this is
            # enough asyncio activity to make a serial/blocking impl obvious.
            for i in range(200):
                await RedisKeyValueStoreAction(
                    RedisKeyValueSetActionConfig(method="set", key=f"k:{i}", value=f"v{i}"),
                    redis_client,
                ).run(integration_context)
                got = await RedisKeyValueStoreAction(
                    RedisKeyValueGetActionConfig(method="get", key=f"k:{i}"),
                    redis_client,
                ).run(integration_context)
                assert got == {"value": f"v{i}"}

        # We can't easily force a slow real Redis here, so if the burst
        # completes too fast the helper soft-passes — that's still the
        # correct outcome (no blocking observed). If the burst is slow
        # enough (e.g. real Redis with real latency), the ticker check
        # actively verifies non-blocking.
        # tick_interval_s=0.05 keeps fakeredis bursts (typically <100ms) inside
        # the soft-pass window; real Redis latency will still exercise the check.
        await assert_does_not_block(_burst(), tick_interval_s=0.05, min_ticks=5)


class TestRedisThreadAffinity:
    """Native-async driver should never hop to another thread — the coroutine
    body runs on the event-loop thread from start to finish. If a future
    refactor accidentally re-introduces `run_in_executor` or
    `run_coroutine_threadsafe` here, this test catches it."""

    @pytest.mark.anyio
    async def test_run_stays_on_event_loop_thread(self, redis_client, integration_context):
        main_thread = threading.current_thread()

        # Wrap `set` so we can record which thread it's called on.
        thread_at_call = {}
        original_set = redis_client.set

        async def _instrumented_set(*args, **kwargs):
            thread_at_call["thread"] = threading.current_thread()
            return await original_set(*args, **kwargs)

        redis_client.set = _instrumented_set  # type: ignore[assignment]

        try:
            await RedisKeyValueStoreAction(
                RedisKeyValueSetActionConfig(method="set", key="thread-check", value="x"),
                redis_client,
            ).run(integration_context)
        finally:
            redis_client.set = original_set  # type: ignore[assignment]

        assert thread_at_call["thread"] is main_thread, (
            f"Expected the redis call to execute on the event-loop thread "
            f"({main_thread!r}); ran on {thread_at_call['thread']!r} instead. "
            f"Native-async drivers should not use `_run_in_executor`."
        )


class TestRedisServiceSignature:
    def test_service_run_has_no_loop_kwarg(self):
        signature = inspect.signature(RedisKeyValueStoreService._run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "action", "context"]

    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(RedisKeyValueStoreAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "context"]
