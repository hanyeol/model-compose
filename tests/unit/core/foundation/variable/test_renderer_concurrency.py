"""Tests covering concurrent and nested rendering invariants:
parallel `*`/`|` iterations must not leak item/index state across each
other, inner scopes must shadow outer ones, and `${item}` must distinguish
"not inside a map/split" from "the item is None"."""

import asyncio
import pytest

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.streaming.iterators import StreamChunkIterator


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_source_resolver(sources):
    async def resolver(key, index=None, scope=None):
        value = sources.get(key)
        if index is not None and isinstance(value, list):
            return value[index]
        return value
    return resolver


async def async_gen(items, delay=0.0):
    for item in items:
        if delay:
            await asyncio.sleep(delay)
        yield item


async def collect_async(iterator):
    return [item async for item in iterator]


def make_stream(items, is_fragmented=True, delay=0.0):
    return StreamChunkIterator(async_gen(items, delay=delay), is_fragmented=is_fragmented)


# ============================================================
# Parallel `*` iterations must not leak item/index state
# ============================================================

class TestParallelMapIsolation:
    """`asyncio.gather` over multiple `*` renders — each coroutine must
    see its own item/index, not another coroutine's."""

    @pytest.mark.anyio
    async def test_gather_parallel_map_renders_with_slow_resolver(self):
        """Two concurrent map renders where the source resolver inserts
        an await on every lookup. During render A's iteration frame, the
        template reads `${item.n}` — if resolving that await yields to
        render B, which pushes its own iteration frame, then A's next
        read of `${item}` sees B's item on stack-top."""

        async def slow_resolver(key, index=None, scope=None):
            # Force a loop yield on every resolution so interleaving
            # happens *inside* each iteration frame.
            await asyncio.sleep(0)
            sources = {
                "a": [{"n": 1}, {"n": 2}, {"n": 3}],
                "b": [{"n": 10}, {"n": 20}, {"n": 30}],
            }
            value = sources.get(key)
            if index is not None and isinstance(value, list):
                return value[index]
            return value

        renderer = VariableRenderer(slow_resolver)

        async def render_many(src):
            results = []
            for _ in range(10):
                r = await renderer.render({
                    "*": f"${{{src}}}",
                    "n": "${item.n}",
                    "src": src,
                })
                results.append(r)
            return results

        a_results, b_results = await asyncio.gather(
            render_many("a"),
            render_many("b"),
        )

        expected_a = [{"n": 1, "src": "a"}, {"n": 2, "src": "a"}, {"n": 3, "src": "a"}]
        expected_b = [{"n": 10, "src": "b"}, {"n": 20, "src": "b"}, {"n": 30, "src": "b"}]
        for r in a_results:
            assert r == expected_a
        for r in b_results:
            assert r == expected_b

    @pytest.mark.anyio
    async def test_parallel_map_with_slow_sibling_read(self):
        """Template references `${item}` AND a resolver-backed `${slow}`.
        The slow key awaits; during that await, a sibling render pushes
        its own frame. When the first render resumes and reads `${item}`
        on the resumed iteration, it must see its own item — not the
        sibling's."""

        async def resolver(key, index=None, scope=None):
            if key == "slow":
                await asyncio.sleep(0.001)
                return "ok"
            return {
                "a": [{"n": 1}, {"n": 2}, {"n": 3}],
                "b": [{"n": 10}, {"n": 20}, {"n": 30}],
            }.get(key)

        renderer = VariableRenderer(resolver)

        async def render_src(src):
            # `slow` field awaits mid-iteration-frame; THEN `${item.n}`
            # is read — if a sibling pushed in between, top is corrupted.
            return await renderer.render({
                "*": f"${{{src}}}",
                "wait": "${slow}",
                "n": "${item.n}",
            })

        a, b = await asyncio.gather(render_src("a"), render_src("b"))

        assert a == [
            {"wait": "ok", "n": 1},
            {"wait": "ok", "n": 2},
            {"wait": "ok", "n": 3},
        ]
        assert b == [
            {"wait": "ok", "n": 10},
            {"wait": "ok", "n": 20},
            {"wait": "ok", "n": 30},
        ]

    @pytest.mark.anyio
    async def test_gather_parallel_map_stream_renders(self):
        """Two concurrent `*` renders over streams — the stream `_iterate`
        closures push to the shared stack and `await` on the next source
        item between push and template render, giving the sibling coroutine
        a chance to overwrite stack-top."""
        s1 = make_stream([{"n": i} for i in range(1, 11)], delay=0.0005)
        s2 = make_stream([{"n": 100 + i} for i in range(1, 11)], delay=0.0005)
        renderer = VariableRenderer(make_source_resolver({"s1": s1, "s2": s2}))

        async def map_and_collect(key):
            result = await renderer.render({
                "*": f"${{{key}}}",
                "v": "${item.n}",
            })
            return await collect_async(result)

        r1, r2 = await asyncio.gather(
            map_and_collect("s1"),
            map_and_collect("s2"),
        )

        assert r1 == [{"v": i} for i in range(1, 11)]
        assert r2 == [{"v": 100 + i} for i in range(1, 11)]

    @pytest.mark.anyio
    async def test_gather_parallel_split_stream_drains(self):
        """Two concurrent `|` splits over separate streams must deliver
        each stream's values intact under interleaved consumption."""
        s1 = make_stream([{"x": 1, "t": "00:00:00.100"},
                          {"x": 2, "t": "00:00:00.200"},
                          {"x": 3, "t": "00:00:00.300"}], delay=0.001)
        s2 = make_stream([{"x": 10, "t": "00:00:01.100"},
                          {"x": 20, "t": "00:00:01.200"},
                          {"x": 30, "t": "00:00:01.300"}], delay=0.001)
        renderer = VariableRenderer(make_source_resolver({"s1": s1, "s2": s2}))

        async def split_and_drain(key):
            result = await renderer.render({
                "|": f"${{{key}}}",
                "x": "${item.x}",
                "t": "${item.t}",
            })
            x = await collect_async(result["x"])
            t = await collect_async(result["t"])
            return x, t

        (x1, t1), (x2, t2) = await asyncio.gather(
            split_and_drain("s1"),
            split_and_drain("s2"),
        )

        assert x1 == [1, 2, 3]
        assert t1 == ["00:00:00.100", "00:00:00.200", "00:00:00.300"]
        assert x2 == [10, 20, 30]
        assert t2 == ["00:00:01.100", "00:00:01.200", "00:00:01.300"]

    @pytest.mark.anyio
    async def test_split_stream_lanes_consumed_concurrently_match(self):
        """Within a single `|` render, draining its lanes concurrently
        must yield matching per-index values on every lane."""
        stream = make_stream(
            [{"x": i, "t": f"00:00:00.{i:03d}"} for i in range(1, 21)],
            delay=0.0005,
        )
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({
            "|": "${s}",
            "x": "${item.x}",
            "t": "${item.t}",
        })

        xs, ts = await asyncio.gather(
            collect_async(result["x"]),
            collect_async(result["t"]),
        )

        assert xs == list(range(1, 21))
        assert ts == [f"00:00:00.{i:03d}" for i in range(1, 21)]


# ============================================================
# Nested `*` inside `*` — inner must shadow outer item/index
# ============================================================

class TestNestedScopeShadow:
    """When `*` is nested inside another `*`, `${item}` must bind to the
    innermost active iteration."""

    @pytest.mark.anyio
    async def test_inner_map_shadows_outer_item(self):
        renderer = VariableRenderer(make_source_resolver({
            "groups": [
                {"id": "g1", "members": [{"n": "a"}, {"n": "b"}]},
                {"id": "g2", "members": [{"n": "c"}]},
            ],
        }))
        result = await renderer.render({
            "*": "${groups}",
            "members": {"*": "${item.members}", "n": "${item.n}"},
        })
        assert result == [
            {"members": [{"n": "a"}, {"n": "b"}]},
            {"members": [{"n": "c"}]},
        ]

    @pytest.mark.anyio
    async def test_inner_index_shadows_outer(self):
        renderer = VariableRenderer(make_source_resolver({
            "outer": [["x", "y"], ["z"]],
        }))
        result = await renderer.render({
            "*": "${outer}",
            "inner": {"*": "${item}", "i": "${index}", "v": "${item}"},
        })
        assert result == [
            {"inner": [{"i": 0, "v": "x"}, {"i": 1, "v": "y"}]},
            {"inner": [{"i": 0, "v": "z"}]},
        ]


# ============================================================
# `${item}` sentinel: outside map/split vs item-is-None
# ============================================================

class TestItemSentinel:
    """`${item}` outside any map/split must defer to the source resolver —
    not resolve to None just because no iteration is active. And inside a
    map whose current item IS None, it must resolve to None (not fall back)."""

    @pytest.mark.anyio
    async def test_item_outside_map_defers_to_resolver(self):
        """`${item}` with no enclosing `*`/`|` must call source_resolver,
        which can supply a value under the key `item`."""
        renderer = VariableRenderer(make_source_resolver({"item": "from-resolver"}))
        assert await renderer.render("${item}") == "from-resolver"

    @pytest.mark.anyio
    async def test_item_inside_map_with_none_item_is_none(self):
        """Inside `*` over `[None, 1]`, the first iteration's `${item}`
        must be None (not fall back to the resolver)."""
        renderer = VariableRenderer(make_source_resolver({
            "v": [None, 1],
            "item": "resolver-should-not-be-used",
        }))
        result = await renderer.render({"*": "${v}", "val": "${item}"})
        assert result == [{"val": None}, {"val": 1}]
