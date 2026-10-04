"""Tests for on-demand idle_timeout — not yet implemented.

Covers the Phase 1 scope:
  - idle_timeout counts down from the last activity; when it elapses while
    the model is IDLE and count==0, the driver.unload_model() must be called
  - a request that arrives before timeout cancels the pending unload
  - a request on an unloaded model triggers reload
  - preload: true also schedules an idle timer (preloaded-but-unused models
    still auto-unload)
  - streaming responses keep the model loaded until the iterator drains
  - shutdown cancels the idle timer and unloads cleanly
  - on_demand not configured  → old behavior (no auto-unload)

All tests use a fake driver that records load/unload calls so we can assert
lifecycle without touching real inference backends.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, List, Optional

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.base.common import ModelTaskDriver
from mindor.core.component.services.model.model import ModelComponent
from mindor.dsl.schema.component.impl.model.tasks.text_classification.impl.huggingface import (
    HuggingfaceTextClassificationModelComponentConfig,
)
from mindor.dsl.schema.component.impl.model.tasks.common import (
    OnDemandConfig,
    OnDemandPriority,
)


class FakeDriver(ModelTaskDriver):
    """Driver stand-in that records lifecycle calls instead of loading real models."""

    def __init__(self, id: str, config: Any, daemon: bool) -> None:
        super().__init__(id, config, daemon)
        self.load_calls: int = 0
        self.unload_calls: int = 0
        self.reclaim_calls: int = 0
        self.run_calls: int = 0
        self.loaded: bool = False
        self._stream_chunks: int = 3
        self._stream_delay: float = 0.05

    async def _load_model(self) -> None:
        self.load_calls += 1
        self.loaded = True

    async def _unload_model(self) -> None:
        self.unload_calls += 1
        self.loaded = False

    async def _run(self, action: Any, context: ComponentActionContext) -> Any:
        self.run_calls += 1
        return {"ok": True, "loaded": self.loaded}


class StreamingFakeDriver(FakeDriver):
    async def _run(self, action: Any, context: ComponentActionContext) -> Any:
        self.run_calls += 1
        chunks = self._stream_chunks
        delay = self._stream_delay
        driver = self

        async def _gen() -> AsyncIterator[str]:
            for i in range(chunks):
                await asyncio.sleep(delay)
                assert driver.loaded, f"driver unloaded mid-stream at chunk {i}"
                yield f"chunk-{i}"

        return _gen()


def _make_config(
    *,
    preload: bool = False,
    on_demand: Any = False,
    max_concurrent_count: int = 0,
) -> HuggingfaceTextClassificationModelComponentConfig:
    return HuggingfaceTextClassificationModelComponentConfig(
        id="fake-model",
        type="model",
        task="text-classification",
        driver="huggingface",
        model={"provider": "huggingface", "repository": "fake/fake"},
        device="cpu",
        runtime={"type": "native"},
        max_concurrent_count=max_concurrent_count,
        actions=[{"id": "classify", "default": True, "text": "stub"}],
        preload=preload,
        on_demand=on_demand,
    )


class FakeModelComponent(ModelComponent):
    """ModelComponent that uses FakeDriver instead of loading real driver modules."""

    _driver_cls: type = FakeDriver

    def _create_driver(self, type: Any, driver: Any) -> ModelTaskDriver:
        return self._driver_cls(self.id, self.config, self.daemon)


# ----- Phase 1 contract tests --------------------------------------------------


def test_idle_timeout_triggers_unload_after_last_request() -> None:
    """After idle_timeout elapses with no activity, driver.unload_model is called."""
    asyncio.run(_scenario_idle_timeout_triggers_unload())


async def _scenario_idle_timeout_triggers_unload() -> None:
    config = _make_config(
        preload=False,
        on_demand=OnDemandConfig(priority=OnDemandPriority.NORMAL, idle_timeout="0.15s"),
    )
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    driver: FakeDriver = component.driver  # type: ignore[assignment]

    await component.setup()
    await component.start()

    assert driver.load_calls == 0, "lazy: should not load at start()"

    await component.run(action_id="__default__", run_id="r1", input={})
    assert driver.load_calls == 1, "first request loads the model"
    assert driver.loaded is True

    # Wait longer than idle_timeout.
    await asyncio.sleep(0.35)

    assert driver.unload_calls == 1, (
        f"idle_timeout expired but unload_model was called {driver.unload_calls} times"
    )
    assert driver.loaded is False

    await component.stop()
    await component.teardown()


def test_request_before_timeout_prevents_unload() -> None:
    """A request arriving before idle_timeout resets the countdown — no unload."""
    asyncio.run(_scenario_request_before_timeout_prevents_unload())


async def _scenario_request_before_timeout_prevents_unload() -> None:
    config = _make_config(
        preload=False,
        on_demand=OnDemandConfig(idle_timeout="0.2s"),
    )
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    driver: FakeDriver = component.driver  # type: ignore[assignment]

    await component.setup()
    await component.start()

    await component.run(action_id="__default__", run_id="r1", input={})
    await asyncio.sleep(0.1)  # under the timeout
    await component.run(action_id="__default__", run_id="r2", input={})
    await asyncio.sleep(0.1)  # still under the second request's timeout

    assert driver.unload_calls == 0, (
        f"model should still be loaded (two requests within timeout window), "
        f"got unload_calls={driver.unload_calls}"
    )
    assert driver.loaded is True

    await component.stop()
    await component.teardown()


def test_reload_on_request_after_unload() -> None:
    """A request after idle unload re-loads the model transparently."""
    asyncio.run(_scenario_reload_after_unload())


async def _scenario_reload_after_unload() -> None:
    config = _make_config(
        preload=False,
        on_demand=OnDemandConfig(idle_timeout="0.1s"),
    )
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    driver: FakeDriver = component.driver  # type: ignore[assignment]

    await component.setup()
    await component.start()

    await component.run(action_id="__default__", run_id="r1", input={})
    await asyncio.sleep(0.25)
    assert driver.unload_calls == 1

    result = await component.run(action_id="__default__", run_id="r2", input={})
    assert driver.load_calls == 2, "second request should trigger reload"
    assert driver.loaded is True
    assert result == {"ok": True, "loaded": True}

    await component.stop()
    await component.teardown()


def test_preloaded_model_auto_unloads_when_unused() -> None:
    """preload: true + on_demand: still auto-unloads after idle_timeout even
    if no request ever arrived."""
    asyncio.run(_scenario_preload_auto_unloads())


async def _scenario_preload_auto_unloads() -> None:
    config = _make_config(
        preload=True,
        on_demand=OnDemandConfig(idle_timeout="0.1s"),
    )
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    driver: FakeDriver = component.driver  # type: ignore[assignment]

    await component.setup()
    await component.start()

    assert driver.load_calls == 1, "preload loads at start"
    assert driver.loaded is True

    await asyncio.sleep(0.25)
    assert driver.unload_calls == 1, (
        "preloaded-but-unused model should auto-unload after idle_timeout"
    )

    await component.stop()
    await component.teardown()


def test_streaming_response_blocks_idle_unload() -> None:
    """While a streaming iterator is being consumed, the model stays loaded;
    idle timer starts only after the stream drains."""
    asyncio.run(_scenario_streaming_blocks_idle_unload())


async def _scenario_streaming_blocks_idle_unload() -> None:
    config = _make_config(
        preload=False,
        on_demand=OnDemandConfig(idle_timeout="0.1s"),
    )
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    component._driver_cls = StreamingFakeDriver  # type: ignore[attr-defined]
    # Reconstruct driver with streaming behavior.
    component.driver = StreamingFakeDriver(component.id, component.config, component.daemon)
    driver: StreamingFakeDriver = component.driver  # type: ignore[assignment]
    driver._stream_chunks = 4
    driver._stream_delay = 0.1  # total stream time = 0.4s, well past idle_timeout

    await component.setup()
    await component.start()

    output = await component.run(action_id="__default__", run_id="r1", input={})
    assert hasattr(output, "__aiter__")

    collected: List[str] = []
    async for chunk in output:
        collected.append(chunk)
        # Each chunk takes 0.1s; by chunk 2 we've exceeded idle_timeout.
        # Driver must still be loaded (assertion inside _gen catches a premature unload).

    assert collected == [f"chunk-{i}" for i in range(4)]
    assert driver.unload_calls == 0, "no unload while streaming"

    # After drain, idle timer fires.
    await asyncio.sleep(0.25)
    assert driver.unload_calls == 1

    await component.stop()
    await component.teardown()


def test_shutdown_cancels_idle_timer_and_unloads() -> None:
    """_stop() must cancel pending idle timers and unload cleanly without
    leaving background tasks."""
    asyncio.run(_scenario_shutdown_cancels_idle_timer())


async def _scenario_shutdown_cancels_idle_timer() -> None:
    config = _make_config(
        preload=True,
        on_demand=OnDemandConfig(idle_timeout="5s"),  # long timeout — would fire well after shutdown
    )
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    driver: FakeDriver = component.driver  # type: ignore[assignment]

    await component.setup()
    await component.start()
    assert driver.loaded is True

    await component.stop()
    await component.teardown()

    assert driver.unload_calls == 1, "stop() must unload the loaded model"
    # Any lingering idle timer task would raise warnings or run after teardown;
    # check that no task referencing the component is still pending.
    pending = [t for t in asyncio.all_tasks() if not t.done() and "idle" in (t.get_name() or "").lower()]
    assert not pending, f"idle timer task not cancelled on shutdown: {pending}"


def test_no_on_demand_means_no_auto_unload() -> None:
    """Regression guard: on_demand not configured  → old behavior,
    model loaded at start and never auto-unloaded."""
    asyncio.run(_scenario_no_on_demand_no_auto_unload())


async def _scenario_no_on_demand_no_auto_unload() -> None:
    config = _make_config(preload=True, on_demand=False)
    component = FakeModelComponent(id="fake-model", config=config, global_configs=None, daemon=False)  # type: ignore[arg-type]
    driver: FakeDriver = component.driver  # type: ignore[assignment]

    await component.setup()
    await component.start()
    assert driver.load_calls == 1

    await asyncio.sleep(0.3)
    assert driver.unload_calls == 0, "without on_demand there must be no auto-unload"
    assert driver.loaded is True

    await component.stop()
    await component.teardown()
    assert driver.unload_calls == 1  # stop() still unloads
