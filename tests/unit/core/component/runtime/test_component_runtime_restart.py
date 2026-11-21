"""Unit tests for ``ComponentRuntimeManager``'s restart supervisor.

Scenarios drive the manager with a fake proxy/channel pair so a crash can
be simulated by latching the proxy's close event. The supervisor should:

- Honour ``policy=NO`` by not spawning a restart task at all.
- Under ``on-failure``, ignore orderly ``stop()`` but relaunch on crash.
- Under ``always``, relaunch on orderly close too.
- Cap attempts via ``max_attempt_count``; ``0`` means unlimited.
- Reset the attempt budget once a relaunch succeeds so a later, unrelated
  crash starts fresh.
- Refuse concurrent ``start()`` (no orphan session).
- Short-circuit ``run()`` with ``ConnectionError`` once gave up.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, List, Optional

import pytest

from mindor.core.component.runtime.common import (
    ComponentRuntimeManager,
    ComponentRuntimeProxy,
)
from mindor.dsl.schema.runtime.impl.common import (
    RuntimeRestartBackoff,
    RuntimeRestartConfig,
    RuntimeRestartPolicy,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeProxy:
    """Mimics the subset of ``ComponentRuntimeProxy`` the manager touches."""

    _counter = 0

    def __init__(self, channel: Any):
        _FakeProxy._counter += 1
        self.id = _FakeProxy._counter
        self.channel = channel
        self._closed = False
        self._closed_event = asyncio.Event()
        self._stop_requested = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    async def wait_until_closed(self) -> None:
        await self._closed_event.wait()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._stop_requested = True
        self._closed = True
        self._closed_event.set()

    async def run(self, *args, **kwargs) -> str:
        if self._closed:
            raise ConnectionError("worker transport closed")
        return "ok"

    def simulate_crash(self) -> None:
        self._closed = True
        self._closed_event.set()


class _FakeManager(ComponentRuntimeManager):
    def __init__(
        self,
        restart_config: RuntimeRestartConfig,
        launch_fails_on: Optional[List[int]] = None,
    ):
        component_config = SimpleNamespace(runtime=SimpleNamespace(restart=restart_config))
        super().__init__("test-worker", component_config, SimpleNamespace())
        self._launch_count = 0
        self._shutdown_count = 0
        self._launch_fails_on = launch_fails_on or []
        self.proxies: List[_FakeProxy] = []

    async def _launch(self) -> Any:
        self._launch_count += 1
        if self._launch_count in self._launch_fails_on:
            raise RuntimeError(f"launch failure on attempt {self._launch_count}")
        return f"channel-{self._launch_count}"

    async def _shutdown(self, channel: Any) -> None:
        self._shutdown_count += 1

    def _create_proxy(self, channel: Any) -> ComponentRuntimeProxy:
        proxy = _FakeProxy(channel)
        self.proxies.append(proxy)
        return proxy  # type: ignore[return-value]

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass


def _policy(policy: RuntimeRestartPolicy, **overrides: Any) -> RuntimeRestartConfig:
    """Short-delay restart config so the supervisor progresses within tests."""
    return RuntimeRestartConfig(
        policy=policy,
        delay=overrides.pop("delay", "10ms"),
        max_delay=overrides.pop("max_delay", "10ms"),
        **overrides,
    )


@pytest.mark.anyio
async def test_start_without_restart_policy_spawns_no_supervisor():
    mgr = _FakeManager(RuntimeRestartConfig(policy=RuntimeRestartPolicy.NO))

    await mgr.start()
    try:
        assert mgr._launch_count == 1
        assert mgr._proxy is not None
        assert mgr._restart_task is None
    finally:
        await mgr.stop()

    assert mgr._shutdown_count == 1
    assert mgr._proxy is None


@pytest.mark.anyio
async def test_double_start_is_rejected():
    mgr = _FakeManager(RuntimeRestartConfig(policy=RuntimeRestartPolicy.NO))
    await mgr.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            await mgr.start()
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_restart_replaces_session():
    mgr = _FakeManager(RuntimeRestartConfig(policy=RuntimeRestartPolicy.NO))
    await mgr.start()
    first = mgr.proxies[-1].id

    await mgr.restart()
    try:
        second = mgr.proxies[-1].id
        assert second != first
        assert mgr._launch_count == 2
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_policy_no_ignores_crashes():
    mgr = _FakeManager(RuntimeRestartConfig(policy=RuntimeRestartPolicy.NO))
    await mgr.start()
    try:
        mgr._proxy.simulate_crash()
        await asyncio.sleep(0.05)
        assert mgr._launch_count == 1
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_on_failure_exits_quietly_on_orderly_stop():
    mgr = _FakeManager(_policy(RuntimeRestartPolicy.ON_FAILURE))

    await mgr.start()
    await mgr.stop()
    await asyncio.sleep(0.05)

    assert mgr._launch_count == 1


@pytest.mark.anyio
async def test_on_failure_relaunches_after_crash():
    mgr = _FakeManager(_policy(RuntimeRestartPolicy.ON_FAILURE, max_attempt_count=3))

    await mgr.start()
    try:
        mgr._proxy.simulate_crash()
        await asyncio.sleep(0.1)
        assert mgr._launch_count >= 2
        assert not mgr._restart_gaveup
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_always_relaunches_after_orderly_close():
    mgr = _FakeManager(_policy(RuntimeRestartPolicy.ALWAYS, max_attempt_count=3))

    await mgr.start()
    try:
        # Trigger an orderly close on the proxy only — the manager itself
        # is not stopping, so `always` should bring a new session up.
        await mgr._proxy.stop()
        await asyncio.sleep(0.1)
        assert mgr._launch_count >= 2
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_gives_up_after_max_attempts_and_run_fails():
    # Make every restart attempt fail: launches 2..5 raise, exhausting a
    # budget of 3 before any succeeds.
    mgr = _FakeManager(
        _policy(RuntimeRestartPolicy.ON_FAILURE, max_attempt_count=3, window="1h"),
        launch_fails_on=[2, 3, 4, 5],
    )

    await mgr.start()
    mgr._proxy.simulate_crash()
    await asyncio.sleep(0.5)

    assert mgr._restart_gaveup
    with pytest.raises(ConnectionError, match="unavailable"):
        await mgr.run("action", "run-id", {})


@pytest.mark.anyio
async def test_max_attempt_count_zero_is_unlimited():
    mgr = _FakeManager(_policy(RuntimeRestartPolicy.ON_FAILURE, max_attempt_count=0))

    await mgr.start()
    try:
        for _ in range(5):
            mgr._proxy.simulate_crash()
            await asyncio.sleep(0.05)

        assert mgr._launch_count >= 6
        assert not mgr._restart_gaveup
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_successful_restart_resets_attempt_budget():
    # A tight budget of 2 within a long window: a successful relaunch must
    # reset the counter or three successive crashes would exhaust it.
    mgr = _FakeManager(_policy(RuntimeRestartPolicy.ON_FAILURE, max_attempt_count=2, window="1h"))

    await mgr.start()
    try:
        for _ in range(3):
            mgr._proxy.simulate_crash()
            await asyncio.sleep(0.05)

        assert mgr._launch_count == 4  # initial + 3 crashes
        assert not mgr._restart_gaveup
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_run_short_circuits_after_gaveup():
    mgr = _FakeManager(RuntimeRestartConfig(policy=RuntimeRestartPolicy.NO))
    await mgr.start()
    try:
        mgr._restart_gaveup = True
        with pytest.raises(ConnectionError, match="unavailable"):
            await mgr.run("action", "run-id", {})
    finally:
        mgr._restart_gaveup = False
        await mgr.stop()


class TestResolveRestartDelay:
    def _mgr(self, **overrides: Any) -> _FakeManager:
        return _FakeManager(
            RuntimeRestartConfig(
                policy=RuntimeRestartPolicy.ON_FAILURE,
                delay=overrides.pop("delay", "1s"),
                max_delay=overrides.pop("max_delay", "10s"),
                backoff=overrides.pop("backoff", RuntimeRestartBackoff.EXPONENTIAL),
                **overrides,
            )
        )

    def test_exponential_doubles_until_max_delay(self):
        mgr = self._mgr()
        assert mgr._resolve_restart_delay(1) == 1.0
        assert mgr._resolve_restart_delay(2) == 2.0
        assert mgr._resolve_restart_delay(3) == 4.0
        assert mgr._resolve_restart_delay(4) == 8.0
        assert mgr._resolve_restart_delay(5) == 10.0  # clamped

    def test_fixed_backoff_is_constant(self):
        mgr = self._mgr(delay="2s", backoff=RuntimeRestartBackoff.FIXED)
        assert mgr._resolve_restart_delay(1) == 2.0
        assert mgr._resolve_restart_delay(3) == 2.0
        assert mgr._resolve_restart_delay(10) == 2.0
