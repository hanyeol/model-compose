"""Shutdown must wait for streaming responses to drain before teardown runs.

Currently ComponentService._active_counter is released the moment _run()
returns, so stop()/teardown() proceed while the iterator is still being
consumed. The same bug exists on the work_queue path (WorkQueue._active_counter
is released when the handler returns, not when its iterator drains).

This file covers three paths:
  1. max_concurrent_count=0, _run() returns a bare async generator
  2. max_concurrent_count=0, _run() returns a StreamIterator (StreamChunkIterator)
  3. max_concurrent_count=1  (work_queue path), returning either shape
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Optional

import pytest

from mindor.core.component.base import ComponentService
from mindor.core.component.context import ComponentActionContext
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.component.impl.common import CommonComponentConfig
from mindor.dsl.schema.component.impl.types import ComponentType
from mindor.dsl.schema.runtime import RuntimeType


class FakeAction(CommonActionConfig):
    id: str = "stream"
    default: bool = True


class FakeComponentConfig(CommonComponentConfig):
    type: ComponentType = ComponentType.SHELL  # arbitrary; we never use type-specific logic


def _make_config(max_concurrent_count: int) -> FakeComponentConfig:
    return FakeComponentConfig(
        id="fake",
        type=ComponentType.SHELL,
        runtime={"type": RuntimeType.NATIVE},
        max_concurrent_count=max_concurrent_count,
        actions=[FakeAction()],
    )


class StreamingFakeComponent(ComponentService):
    """A component whose _run() returns an iterator that is still being
    produced after _run() itself has returned. Teardown must wait for the
    iterator to drain, otherwise `resource_alive` flips to False mid-stream.
    """

    def __init__(self, *, max_concurrent_count: int, wrap_as_stream_iterator: bool) -> None:
        super().__init__(
            id="fake",
            config=_make_config(max_concurrent_count),
            global_configs=None,  # type: ignore[arg-type]
            daemon=False,
        )
        self._wrap_as_stream_iterator: bool = wrap_as_stream_iterator
        self.resource_alive: bool = True
        self.chunks_produced: int = 0
        self.teardown_at_chunk: Optional[int] = None

    async def _setup(self) -> None:
        self.resource_alive = True

    async def _teardown(self) -> None:
        # Simulates driver teardown — frees the model / closes the connection.
        # Record which chunk the consumer was on when teardown ran, so the
        # test can prove whether the stream had already drained.
        self.teardown_at_chunk = self.chunks_produced
        self.resource_alive = False

    async def _run(self, action: Any, context: ComponentActionContext) -> Any:
        parent = self

        async def _gen() -> AsyncIterator[str]:
            for i in range(5):
                # Yield to the loop so the consumer can be preempted by shutdown.
                await asyncio.sleep(0.05)
                if not parent.resource_alive:
                    raise RuntimeError(
                        f"resource torn down while stream was still being consumed "
                        f"(chunk {i}): component was stopped before iterator drained"
                    )
                parent.chunks_produced += 1
                yield f"chunk-{i}"

        if self._wrap_as_stream_iterator:
            return StreamChunkIterator(_gen())
        return _gen()


# Covers the two output shapes a component can hand back (bare async generator
# vs StreamIterator subclass) crossed with the two concurrency paths
# (direct _run() vs work_queue). ids make failures easy to attribute.
@pytest.mark.parametrize(
    "max_concurrent_count,wrap_as_stream_iterator",
    [
        (0, False),  # direct path, bare async generator
        (0, True),   # direct path, StreamChunkIterator
        (1, False),  # work_queue path, bare async generator
        (1, True),   # work_queue path, StreamChunkIterator
    ],
    ids=[
        "direct-asyncgen",
        "direct-streamiterator",
        "workqueue-asyncgen",
        "workqueue-streamiterator",
    ],
)
def test_shutdown_waits_for_streaming_response_to_drain(
    max_concurrent_count: int,
    wrap_as_stream_iterator: bool,
) -> None:
    """stop() + teardown() must not complete until the streaming iterator
    returned by run() has been fully consumed. Any chunk delivered after
    teardown would mean the consumer is reading from a dead resource.
    """
    asyncio.run(
        _scenario_shutdown_waits_for_stream(
            max_concurrent_count=max_concurrent_count,
            wrap_as_stream_iterator=wrap_as_stream_iterator,
        )
    )


async def _scenario_shutdown_waits_for_stream(
    *,
    max_concurrent_count: int,
    wrap_as_stream_iterator: bool,
) -> None:
    component = StreamingFakeComponent(
        max_concurrent_count=max_concurrent_count,
        wrap_as_stream_iterator=wrap_as_stream_iterator,
    )
    await component.setup()
    await component.start()

    collected = []
    stream_error: Optional[BaseException] = None

    output = await component.run(
        action_id="__default__",
        run_id="run-1",
        input={},
    )

    assert hasattr(output, "__aiter__"), "expected a streaming iterator"

    # Start consuming the stream in a background task so we can race shutdown
    # against it.
    async def _consume() -> None:
        nonlocal stream_error
        try:
            async for chunk in output:
                collected.append(chunk)
        except BaseException as e:
            stream_error = e

    consumer = asyncio.create_task(_consume())

    # Let the consumer pull a chunk, then kick off shutdown while the iterator
    # is still open. Correct behavior: shutdown blocks until the consumer
    # finishes draining.
    await asyncio.sleep(0.07)

    async def _shutdown() -> None:
        await component.stop()
        await component.teardown()

    shutdown_task = asyncio.create_task(_shutdown())

    # Give shutdown enough wall time to complete *if* it incorrectly returns
    # early (the current buggy path). Correct behavior: it stays blocked here
    # because the stream is still draining.
    try:
        await asyncio.wait_for(asyncio.shield(shutdown_task), timeout=0.15)
        shutdown_returned_early = True
    except asyncio.TimeoutError:
        shutdown_returned_early = False

    # Wait for the consumer to finish on its own.
    await asyncio.wait_for(consumer, timeout=2.0)

    # And now shutdown should complete cleanly.
    await asyncio.wait_for(shutdown_task, timeout=2.0)

    # Core assertion: shutdown must NOT have returned before the stream drained.
    assert not shutdown_returned_early, (
        "shutdown (stop + teardown) returned while the streaming iterator was still "
        f"open. Consumer had collected {len(collected)} / 5 chunks at the moment "
        f"shutdown finished. _active_counter is being released before the stream drains."
    )

    # The consumer must have seen all 5 chunks with no error.
    assert stream_error is None, (
        f"consumer errored because the resource was torn down mid-stream: {stream_error!r}"
    )
    assert collected == [f"chunk-{i}" for i in range(5)], (
        f"stream was interrupted; got {collected}"
    )

    # Teardown must have run only after all chunks were produced.
    assert component.teardown_at_chunk == 5, (
        f"teardown ran after only {component.teardown_at_chunk} chunks were produced; "
        f"expected 5 (full drain before teardown)"
    )
