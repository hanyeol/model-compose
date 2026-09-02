"""Unit tests for FanOutJob and its private FanOutPump helper.

Covers the input-shape matrix from `docs/specs/fan-out-job-spec.md` §2.1:

- Single `StreamResource`, copyable — cheap `resource.copy(count)` path.
- Single `StreamResource`, non-copyable — pump-and-fanout + `resource.tee(sources)`.
- `StreamChunkIterator` input — pump + `StreamChunkIterator` re-wrap preserving
  `is_fragmented`.
- Bare `AsyncIterator` / `list` / scalar input — container-level pump.

The FanOutPump behavioral tests exercise the invariants called out in the spec
(§3, §6): backpressure under uneven consumers, single-branch early close, all
branches close, source exception propagation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections.abc import AsyncIterator

import asyncio
import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.resources import StreamResource, TeeStreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl.fan_out import FanOutJob, FanOutPump, SpooledStreamResource
from mindor.dsl.schema.job import JobConfig
import os


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ------------------------------------------------------------------ #
# Fakes shared across tests                                          #
# ------------------------------------------------------------------ #

class FakeWorkflow:
    def __init__(self):
        self.task_id = "task-test"
        self.workflow_id = "wf-test"


class FakeJobContext:
    def __init__(self):
        self.workflow = FakeWorkflow()
        self.is_terminal = False
        self.cancellation_token = None
        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self.renderer = VariableRenderer(self.resolve_source)

    def register_source(self, scope: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(scope or "__global__", {})[key] = source

    async def render_variable(self, scope: Optional[str], value: Any, skip_decode: bool = False) -> Any:
        return await self.renderer.render(value, scope, skip_decode=skip_decode)

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})
        if key in sources:
            value = sources[key]
            return value[index] if index is not None and isinstance(value, list) else value
        return None


class NonCopyableBytesStream(StreamResource):
    """StreamResource that reports copyable=False so the fan-out job takes the
    pump + `tee(sources)` path. Uses the base tee default which returns
    TeeStreamResource wrappers (group A per stream-resource-tee-spec §1).
    """
    def __init__(self, chunks: List[bytes]):
        super().__init__(content_type="application/octet-stream", filename=None, size=sum(len(c) for c in chunks))
        self._chunks = chunks

    async def close(self) -> None:
        pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


def _cfg(raw: dict):
    return TypeAdapter(JobConfig).validate_python({ "type": "fan-out", **raw })


def _make_job(cfg) -> FanOutJob:
    job = FanOutJob.__new__(FanOutJob)
    job.id = "test-fan-out"
    job.config = cfg
    job.global_configs = None
    job._on_start = None
    job._started_fired = False
    return job


async def _drain(source: AsyncIterator[Any]) -> List[Any]:
    return [ item async for item in source ]


async def _drain_stream_resource(resource: StreamResource) -> bytes:
    buffer = bytearray()
    async for chunk in resource:
        buffer.extend(chunk)
    return bytes(buffer)


# ------------------------------------------------------------------ #
# FanOutJob._run — copyable StreamResource                           #
# ------------------------------------------------------------------ #

class TestCopyableStreamResource:

    @pytest.mark.anyio
    async def test_bytes_stream_resource_two_way(self):
        # BytesStreamResource.copyable() is True → resource.copy(2) path.
        # Branches must be independent BytesStreamResource instances that
        # each yield the full payload.
        source = BytesStreamResource(b"hello-world", content_type="text/plain", filename="a.txt")

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "left", "right" ],
        }))

        result = await job._run(context)

        assert set(result.keys()) == { "left", "right" }
        for branch in result.values():
            assert isinstance(branch, BytesStreamResource)
            assert branch is not source
            # content_type / filename must be carried by constructor reuse.
            assert branch.content_type == "text/plain"
            assert branch.filename == "a.txt"

        assert await _drain_stream_resource(result["left"]) == b"hello-world"
        assert await _drain_stream_resource(result["right"]) == b"hello-world"

    @pytest.mark.anyio
    async def test_copy_branches_are_independent(self):
        # Reading one branch to completion must not affect the other.
        source = BytesStreamResource(b"abcdef")

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        assert await _drain_stream_resource(result["a"]) == b"abcdef"
        assert await _drain_stream_resource(result["b"]) == b"abcdef"


# ------------------------------------------------------------------ #
# FanOutJob._run — non-copyable StreamResource                       #
# ------------------------------------------------------------------ #

class TestNonCopyableStreamResource:

    @pytest.mark.anyio
    async def test_non_copyable_uses_tee_wrapper(self):
        # copyable=False → pump-and-fanout + resource.tee(sources).
        # Base tee default returns TeeStreamResource wrappers.
        source = NonCopyableBytesStream([ b"chunk-1", b"chunk-2", b"chunk-3" ])

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        assert set(result.keys()) == { "a", "b" }
        for branch in result.values():
            assert isinstance(branch, TeeStreamResource)

        # Concurrent drain: both branches must see the same byte sequence.
        drained_a, drained_b = await asyncio.gather(
            _drain_stream_resource(result["a"]),
            _drain_stream_resource(result["b"]),
        )
        assert drained_a == b"chunk-1chunk-2chunk-3"
        assert drained_b == b"chunk-1chunk-2chunk-3"


# ------------------------------------------------------------------ #
# FanOutJob._run — spool mode                                        #
# ------------------------------------------------------------------ #

class TestSpoolMode:

    @pytest.mark.anyio
    async def test_spool_returns_file_backed_branches(self):
        # spool: true on a non-copyable StreamResource → each branch is a
        # SpooledStreamResource backed by a shared tempfile.
        source = NonCopyableBytesStream([ b"alpha-", b"beta-", b"gamma" ])

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
            "spool": True,
        }))

        result = await job._run(context)

        assert set(result.keys()) == { "a", "b" }
        for branch in result.values():
            assert isinstance(branch, SpooledStreamResource)
            assert branch.content_type == "application/octet-stream"

        drained_a, drained_b = await asyncio.gather(
            _drain_stream_resource(result["a"]),
            _drain_stream_resource(result["b"]),
        )
        assert drained_a == b"alpha-beta-gamma"
        assert drained_b == b"alpha-beta-gamma"

    @pytest.mark.anyio
    async def test_spool_branches_advance_independently(self):
        # Slow reader on branch A must not stall branch B: with spool the
        # writer runs ahead into the tempfile and B reads at its own pace.
        source = NonCopyableBytesStream([ b"x" * 4096 for _ in range(8) ])

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "slow", "fast" ],
            "spool": True,
        }))

        result = await job._run(context)

        async def _slow_drain(resource):
            buffer = bytearray()
            async for chunk in resource:
                await asyncio.sleep(0)
                buffer.extend(chunk)
            return bytes(buffer)

        slow, fast = await asyncio.gather(
            _slow_drain(result["slow"]),
            _drain_stream_resource(result["fast"]),
        )
        assert slow == b"x" * 32768
        assert fast == b"x" * 32768

    @pytest.mark.anyio
    async def test_spool_deletes_tempfile_after_all_branches_close(self):
        source = NonCopyableBytesStream([ b"data" ])

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
            "spool": True,
        }))

        result = await job._run(context)
        spool_path = result["a"]._spooler.path

        # Drain and close both branches — the tempfile must be deleted only
        # after the last branch's close() releases the spool's ref count.
        await asyncio.gather(
            _drain_stream_resource(result["a"]),
            _drain_stream_resource(result["b"]),
        )
        assert os.path.exists(spool_path)

        await result["a"].close()
        assert os.path.exists(spool_path)

        await result["b"].close()
        assert not os.path.exists(spool_path)

    @pytest.mark.anyio
    async def test_spool_is_copyable(self):
        # SpooledStreamResource reports copyable=True so a downstream fan-out
        # can further split it via cheap constructor reuse.
        source = NonCopyableBytesStream([ b"payload" ])

        context = FakeJobContext()
        context.register_source(None, "source", source)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
            "spool": True,
        }))

        result = await job._run(context)
        assert result["a"].copyable() is True

        # Copy one branch into two more — all three should drain the same bytes.
        extras = result["a"].copy(2)
        drained_a2, drained_b, drained_e0, drained_e1 = await asyncio.gather(
            _drain_stream_resource(result["a"]),
            _drain_stream_resource(result["b"]),
            _drain_stream_resource(extras[0]),
            _drain_stream_resource(extras[1]),
        )
        assert drained_a2 == b"payload"
        assert drained_b == b"payload"
        assert drained_e0 == b"payload"
        assert drained_e1 == b"payload"

    @pytest.mark.anyio
    async def test_spool_ignored_on_container_input(self):
        # `spool: true` is only meaningful for a single StreamResource.
        # For container inputs the fan-out logs a warning and falls back to
        # the ordinary in-memory pump path — the workflow keeps running.
        context = FakeJobContext()
        context.register_source(None, "source", [ 1, 2, 3 ])
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
            "spool": True,
        }))

        result = await job._run(context)

        drained_a, drained_b = await asyncio.gather(_drain(result["a"]), _drain(result["b"]))
        assert drained_a == [ 1, 2, 3 ]
        assert drained_b == [ 1, 2, 3 ]


# ------------------------------------------------------------------ #
# FanOutJob._run — StreamChunkIterator                               #
# ------------------------------------------------------------------ #

class TestStreamChunkIteratorInput:

    @pytest.mark.anyio
    async def test_two_way_preserves_is_fragmented_true(self):
        async def _source():
            for chunk in [ b"x", b"y", b"z" ]:
                yield chunk

        chunks = StreamChunkIterator(_source(), is_fragmented=True)

        context = FakeJobContext()
        context.register_source(None, "source", chunks)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        assert isinstance(result["a"], StreamChunkIterator)
        assert isinstance(result["b"], StreamChunkIterator)
        # Both wrappers must carry the flag from the source.
        assert result["a"].is_fragmented is True
        assert result["b"].is_fragmented is True

        drained_a, drained_b = await asyncio.gather(_drain(result["a"]), _drain(result["b"]))
        assert drained_a == [ b"x", b"y", b"z" ]
        assert drained_b == [ b"x", b"y", b"z" ]

    @pytest.mark.anyio
    async def test_two_way_preserves_is_fragmented_false(self):
        async def _source():
            yield b"only"

        chunks = StreamChunkIterator(_source(), is_fragmented=False)

        context = FakeJobContext()
        context.register_source(None, "source", chunks)
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        assert result["a"].is_fragmented is False
        assert result["b"].is_fragmented is False


# ------------------------------------------------------------------ #
# FanOutJob._run — bare AsyncIterator / list / scalar                #
# ------------------------------------------------------------------ #

class TestContainerFanout:

    @pytest.mark.anyio
    async def test_bare_async_iterator_three_way(self):
        async def _source():
            for i in range(5):
                yield i

        context = FakeJobContext()
        context.register_source(None, "source", _source())
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b", "c" ],
        }))

        result = await job._run(context)

        drained = await asyncio.gather(*(_drain(result[name]) for name in ("a", "b", "c")))
        for items in drained:
            assert items == [ 0, 1, 2, 3, 4 ]

    @pytest.mark.anyio
    async def test_list_input_broadcasts_each_element(self):
        context = FakeJobContext()
        context.register_source(None, "source", [ 10, 20, 30 ])
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        drained_a, drained_b = await asyncio.gather(_drain(result["a"]), _drain(result["b"]))
        assert drained_a == [ 10, 20, 30 ]
        assert drained_b == [ 10, 20, 30 ]

    @pytest.mark.anyio
    async def test_scalar_input_yields_single_item_per_branch(self):
        # BatchSourceIterator wraps a scalar as a single-item source.
        context = FakeJobContext()
        context.register_source(None, "source", "single-value")
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        drained_a, drained_b = await asyncio.gather(_drain(result["a"]), _drain(result["b"]))
        assert drained_a == [ "single-value" ]
        assert drained_b == [ "single-value" ]

    @pytest.mark.anyio
    async def test_empty_list_yields_empty_branches(self):
        context = FakeJobContext()
        context.register_source(None, "source", [])
        job = _make_job(_cfg({
            "input": "${source}",
            "output": [ "a", "b" ],
        }))

        result = await job._run(context)

        drained_a, drained_b = await asyncio.gather(_drain(result["a"]), _drain(result["b"]))
        assert drained_a == []
        assert drained_b == []


# ------------------------------------------------------------------ #
# FanOutPump — behavioral tests                                      #
# ------------------------------------------------------------------ #

class TestFanOutPump:

    @pytest.mark.anyio
    async def test_single_branch_full_drain(self):
        async def _source():
            for i in range(4):
                yield i

        pump = FanOutPump(_source(), count=1)
        [ branch ] = pump.branches()

        assert await _drain(branch) == [ 0, 1, 2, 3 ]

    @pytest.mark.anyio
    async def test_broadcast_to_all_branches(self):
        async def _source():
            for i in range(3):
                yield i

        pump = FanOutPump(_source(), count=3)
        branches = pump.branches()

        drained = await asyncio.gather(*(_drain(b) for b in branches))
        for items in drained:
            assert items == [ 0, 1, 2 ]

    @pytest.mark.anyio
    async def test_slow_consumer_applies_backpressure(self):
        # Emit more items than any single queue can hold. Without backpressure
        # the source would race ahead and either overflow the queue (asyncio
        # queue would block on put) or leak items. With backpressure the pump
        # blocks on the slow branch and everything stays consistent.
        emitted = 0

        async def _source():
            nonlocal emitted
            for i in range(10):
                emitted += 1
                yield i

        pump = FanOutPump(_source(), count=2, buffer_size=2)
        fast, slow = pump.branches()

        async def _slow_drain(source):
            items = []
            async for item in source:
                await asyncio.sleep(0)  # yield control so the fast side runs
                items.append(item)
            return items

        fast_items, slow_items = await asyncio.gather(_drain(fast), _slow_drain(slow))
        assert fast_items == list(range(10))
        assert slow_items == list(range(10))
        assert emitted == 10

    @pytest.mark.anyio
    async def test_early_close_of_one_branch_does_not_stall_others(self):
        # A branch that stops iterating early must drain its queue so the pump
        # unblocks and the surviving branch reaches EOF.
        async def _source():
            for i in range(6):
                yield i

        pump = FanOutPump(_source(), count=2, buffer_size=1)
        first, second = pump.branches()

        # Consume the first branch fully; abort the second after one item.
        async def _abort_after_one(source):
            items = []
            async for item in source:
                items.append(item)
                break
            await source.aclose()
            return items

        first_items, second_items = await asyncio.gather(
            _drain(first),
            _abort_after_one(second),
        )
        assert first_items == list(range(6))
        assert len(second_items) == 1

    @pytest.mark.anyio
    async def test_all_branches_close_cancels_pump(self):
        # If every branch closes before the source is exhausted the pump task
        # must be cancelled — otherwise it would sit forever waiting on put().
        pump_iterations = 0

        async def _source():
            nonlocal pump_iterations
            try:
                for i in range(100):
                    pump_iterations += 1
                    yield i
            finally:
                # Give the pump a chance to observe cancellation.
                pass

        pump = FanOutPump(_source(), count=2, buffer_size=1)
        a, b = pump.branches()

        async def _abort(source):
            async for _ in source:
                await source.aclose()
                return

        await asyncio.gather(_abort(a), _abort(b))

        # Wait a few event loop turns so cancellation can propagate.
        for _ in range(5):
            await asyncio.sleep(0)

        assert pump._pump_task.cancelled() or pump._pump_task.done()
        # Source should not have been drained end-to-end.
        assert pump_iterations < 100

    @pytest.mark.anyio
    async def test_source_exception_propagates_to_all_branches(self):
        class BoomError(RuntimeError):
            pass

        async def _source():
            yield 1
            yield 2
            raise BoomError("boom")

        pump = FanOutPump(_source(), count=2)
        a, b = pump.branches()

        async def _consume(source):
            with pytest.raises(BoomError):
                async for _ in source:
                    pass

        await asyncio.gather(_consume(a), _consume(b))

    @pytest.mark.anyio
    async def test_empty_source_signals_immediate_eof(self):
        async def _source():
            if False:
                yield  # pragma: no cover

        pump = FanOutPump(_source(), count=3)
        branches = pump.branches()

        drained = await asyncio.gather(*(_drain(b) for b in branches))
        for items in drained:
            assert items == []
