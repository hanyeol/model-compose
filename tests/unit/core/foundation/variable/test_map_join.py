"""Tests for `_render_map` (`*`), `_render_join` (`+`), and `_render_split` (`|`)
operators — static, streaming, and nested combinations."""

import asyncio
import pytest

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.streaming.iterators import StreamChunkIterator


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

def make_source_resolver(sources):
    async def resolver(key, index=None, scope=None):
        value = sources.get(key)
        if index is not None and isinstance(value, list):
            return value[index]
        return value
    return resolver


async def async_gen(items):
    for item in items:
        yield item


async def collect_async(iterator):
    return [item async for item in iterator]


def make_stream(items, is_fragmented=True):
    return StreamChunkIterator(async_gen(items), is_fragmented=is_fragmented)


# ============================================================
# `+` (join) — sync inputs
# ============================================================

class TestJoinStatic:
    """Join operator over materialized lists."""

    @pytest.mark.anyio
    async def test_list_of_lists_flatten(self):
        renderer = VariableRenderer(make_source_resolver({"v": [[1, 2], [3, 4], [5]]}))
        assert await renderer.render({"+": "${v}"}) == [1, 2, 3, 4, 5]

    @pytest.mark.anyio
    async def test_list_of_dicts_merge_last_wins(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": {"x": 1, "y": 2},
            "b": {"y": 99, "z": 3},
        }))
        assert await renderer.render({"+": ["${a}", "${b}"]}) == {"x": 1, "y": 99, "z": 3}

    @pytest.mark.anyio
    async def test_list_of_strings_concat(self):
        renderer = VariableRenderer(make_source_resolver({"p": "hello, ", "n": "world"}))
        assert await renderer.render({"+": ["${p}", "${n}", "!"]}) == "hello, world!"

    @pytest.mark.anyio
    async def test_empty_list_returns_none(self):
        renderer = VariableRenderer(make_source_resolver({}))
        assert await renderer.render({"+": []}) is None

    @pytest.mark.anyio
    async def test_all_none_returns_none(self):
        renderer = VariableRenderer(make_source_resolver({"a": None, "b": None}))
        assert await renderer.render({"+": ["${a}", "${b}"]}) is None

    @pytest.mark.anyio
    async def test_none_elements_filtered(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": "x", "b": None, "c": "y",
        }))
        assert await renderer.render({"+": ["${a}", "${b}", "${c}"]}) == "xy"

    @pytest.mark.anyio
    async def test_source_none_returns_none(self):
        renderer = VariableRenderer(make_source_resolver({"v": None}))
        assert await renderer.render({"+": "${v}"}) is None


# ============================================================
# `+` (join) — streaming inputs
# ============================================================

class TestJoinStream:
    """Join operator with stream inputs."""

    @pytest.mark.anyio
    async def test_stream_of_lists_flatten(self):
        stream = make_stream([[1, 2], [3, 4], [5]])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": "${s}"})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True
        assert await collect_async(result) == [1, 2, 3, 4, 5]

    @pytest.mark.anyio
    async def test_stream_of_streams_flatten(self):
        inner1 = make_stream(["a", "b"])
        inner2 = make_stream(["c"])
        outer = make_stream([inner1, inner2])
        renderer = VariableRenderer(make_source_resolver({"s": outer}))
        result = await renderer.render({"+": "${s}"})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True
        assert await collect_async(result) == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_stream_of_dicts_passthrough(self):
        """Dict chunks in a stream are treated as completed values (like str)."""
        stream = make_stream([{"a": 1}, {"b": 2}, {"c": 3}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": "${s}"})
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == [{"a": 1}, {"b": 2}, {"c": 3}]

    @pytest.mark.anyio
    async def test_stream_of_strs_passthrough(self):
        """Str chunks in a stream are treated as completed values."""
        stream = make_stream(["hi", "there"])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": "${s}"})
        assert await collect_async(result) == ["hi", "there"]

    @pytest.mark.anyio
    async def test_stream_skips_none_chunks(self):
        stream = make_stream([[1], None, [2, 3], None])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": "${s}"})
        assert await collect_async(result) == [1, 2, 3]

    @pytest.mark.anyio
    async def test_stream_result_is_always_fragmented(self):
        """`+` collapses inputs into one logical value, so the resulting
        stream is always fragmented — regardless of the source's flag."""
        stream = make_stream([[1]], is_fragmented=False)
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": "${s}"})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True


# ============================================================
# `+` (join) — list with stream elements → promoted to stream
# ============================================================

class TestJoinPromotion:
    """When a static list has stream elements, the whole thing becomes a stream."""

    @pytest.mark.anyio
    async def test_stream_then_sentinel_list(self):
        stream = make_stream([{"title": "a"}, {"title": "b"}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({
            "+": ["${s}", [{"type": "eof"}]],
        })
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True
        assert await collect_async(result) == [
            {"title": "a"},
            {"title": "b"},
            {"type": "eof"},
        ]

    @pytest.mark.anyio
    async def test_mixed_stream_list_str(self):
        stream = make_stream(["x", "y"])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": ["${s}", ["z"], "!"]})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True
        assert await collect_async(result) == ["x", "y", "z", "!"]

    @pytest.mark.anyio
    async def test_promoted_stream_skips_none_elements(self):
        stream = make_stream(["x"])
        renderer = VariableRenderer(make_source_resolver({"s": stream, "n": None}))
        result = await renderer.render({"+": ["${s}", "${n}", ["y"]]})
        assert await collect_async(result) == ["x", "y"]


# ============================================================
# `*` (map) — static and streaming inputs
# ============================================================

class TestMap:
    """Map operator, static and streaming."""

    @pytest.mark.anyio
    async def test_map_no_template_returns_source(self):
        renderer = VariableRenderer(make_source_resolver({"v": [1, 2, 3]}))
        assert await renderer.render({"*": "${v}"}) == [1, 2, 3]

    @pytest.mark.anyio
    async def test_map_with_template(self):
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"text": "a"}, {"text": "b"}],
        }))
        result = await renderer.render({"*": "${v}", "title": "${item.text}"})
        assert result == [{"title": "a"}, {"title": "b"}]

    @pytest.mark.anyio
    async def test_map_over_stream_no_template(self):
        stream = make_stream([1, 2, 3])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"*": "${s}"})
        # No template → source returned as-is (still a stream).
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == [1, 2, 3]

    @pytest.mark.anyio
    async def test_map_over_stream_with_template(self):
        stream = make_stream([{"n": 1}, {"n": 2}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"*": "${s}", "v": "${item.n}"})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True
        assert await collect_async(result) == [{"v": 1}, {"v": 2}]

    @pytest.mark.anyio
    async def test_map_none_source_returns_empty_list(self):
        renderer = VariableRenderer(make_source_resolver({"v": None}))
        assert await renderer.render({"*": "${v}"}) == []


# ============================================================
# Nested `+` around `*`
# ============================================================

class TestJoinAroundMap:
    """`+` wrapping `*` — merging or flattening mapped output."""

    @pytest.mark.anyio
    async def test_join_of_two_mapped_lists(self):
        renderer = VariableRenderer(make_source_resolver({
            "users": [{"name": "alice"}, {"name": "bob"}],
            "extras": [{"name": "carol"}],
        }))
        result = await renderer.render({
            "+": [
                {"*": "${users}", "n": "${item.name}"},
                {"*": "${extras}", "n": "${item.name}"},
            ],
        })
        assert result == [{"n": "alice"}, {"n": "bob"}, {"n": "carol"}]

    @pytest.mark.anyio
    async def test_join_of_mapped_list_with_sentinel(self):
        renderer = VariableRenderer(make_source_resolver({
            "items": [{"text": "a"}, {"text": "b"}],
        }))
        result = await renderer.render({
            "+": [
                {"*": "${items}", "title": "${item.text}"},
                [{"type": "eof"}],
            ],
        })
        assert result == [{"title": "a"}, {"title": "b"}, {"type": "eof"}]

    @pytest.mark.anyio
    async def test_join_of_mapped_stream_with_sentinel(self):
        stream = make_stream([{"text": "a"}, {"text": "b"}, {"text": "c"}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({
            "+": [
                {"*": "${s}", "title": "${item.text}"},
                [{"type": "eof"}],
            ],
        })
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True
        assert await collect_async(result) == [
            {"title": "a"},
            {"title": "b"},
            {"title": "c"},
            {"type": "eof"},
        ]

    @pytest.mark.anyio
    async def test_join_wraps_single_mapped_stream(self):
        stream = make_stream([{"n": 1}, {"n": 2}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({
            "+": [{"*": "${s}", "val": "${item.n}"}],
        })
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == [{"val": 1}, {"val": 2}]


# ============================================================
# Nested `*` inside `+` output template
# ============================================================

class TestDeepNesting:
    @pytest.mark.anyio
    async def test_two_streams_merged(self):
        s1 = make_stream(["a", "b"])
        s2 = make_stream(["c", "d"])
        renderer = VariableRenderer(make_source_resolver({"s1": s1, "s2": s2}))
        result = await renderer.render({"+": ["${s1}", "${s2}"]})
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == ["a", "b", "c", "d"]

    @pytest.mark.anyio
    async def test_stream_of_lists_then_static_list(self):
        """`+` flattens exactly one level: iterating the stream element yields
        its chunks (which are themselves lists), so those list chunks pass
        through unchanged alongside the unrolled sentinel list."""
        stream = make_stream([[1, 2], [3]])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"+": ["${s}", [99]]})
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == [[1, 2], [3], 99]


# ============================================================
# `|` (split) — static inputs
# ============================================================

class TestSplitStatic:
    """Split operator over materialized lists — partitions items into
    parallel per-field collections."""

    @pytest.mark.anyio
    async def test_split_dict_template(self):
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        }))
        result = await renderer.render({
            "|": "${v}",
            "a": "${item.x}",
            "b": "${item.y}",
        })
        assert result == {"a": [1, 3], "b": [2, 4]}

    @pytest.mark.anyio
    async def test_split_uses_index(self):
        renderer = VariableRenderer(make_source_resolver({"v": ["a", "b", "c"]}))
        result = await renderer.render({
            "|": "${v}",
            "value": "${item}",
            "position": "${index}",
        })
        assert result == {"value": ["a", "b", "c"], "position": [0, 1, 2]}

    @pytest.mark.anyio
    async def test_split_missing_field_yields_none(self):
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"x": 1}, {"x": 2}],
        }))
        result = await renderer.render({
            "|": "${v}",
            "x": "${item.x}",
            "y": "${item.y}",
        })
        assert result == {"x": [1, 2], "y": [None, None]}

    @pytest.mark.anyio
    async def test_split_empty_source(self):
        renderer = VariableRenderer(make_source_resolver({"v": []}))
        result = await renderer.render({
            "|": "${v}",
            "a": "${item.x}",
            "b": "${item.y}",
        })
        assert result == {"a": [], "b": []}

    @pytest.mark.anyio
    async def test_split_none_source(self):
        renderer = VariableRenderer(make_source_resolver({"v": None}))
        result = await renderer.render({
            "|": "${v}",
            "a": "${item.x}",
            "b": "${item.y}",
        })
        assert result == {"a": [], "b": []}

    @pytest.mark.anyio
    async def test_split_without_template_raises(self):
        renderer = VariableRenderer(make_source_resolver({"v": [1, 2]}))
        with pytest.raises(ValueError):
            await renderer.render({"|": "${v}"})

    @pytest.mark.anyio
    async def test_split_non_iterable_raises(self):
        renderer = VariableRenderer(make_source_resolver({"v": 42}))
        with pytest.raises(TypeError):
            await renderer.render({"|": "${v}", "x": "${item}"})


# ============================================================
# `|` (split) — streaming inputs
# ============================================================

class TestSplitStream:
    """Split operator over stream input — each output field becomes its own
    stream that yields values in source order as the source is drained."""

    @pytest.mark.anyio
    async def test_split_stream_sequential_drain(self):
        stream = make_stream([{"x": 1, "y": 2}, {"x": 3, "y": 4}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({
            "|": "${s}",
            "a": "${item.x}",
            "b": "${item.y}",
        })
        assert set(result.keys()) == {"a", "b"}
        assert isinstance(result["a"], StreamChunkIterator)
        assert isinstance(result["b"], StreamChunkIterator)

        # Drain `a` fully first, then `b` — buffering must preserve `b`'s
        # values while `a` advances the source.
        a_values = await collect_async(result["a"])
        b_values = await collect_async(result["b"])
        assert a_values == [1, 3]
        assert b_values == [2, 4]

    @pytest.mark.anyio
    async def test_split_stream_concurrent_drain(self):
        stream = make_stream([{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({
            "|": "${s}",
            "a": "${item.x}",
            "b": "${item.y}",
        })
        a_values, b_values = await asyncio.gather(
            collect_async(result["a"]),
            collect_async(result["b"]),
        )
        assert a_values == [1, 3, 5]
        assert b_values == [2, 4, 6]

    @pytest.mark.anyio
    async def test_split_stream_preserves_is_fragmented(self):
        stream = make_stream([{"x": 1}], is_fragmented=False)
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"|": "${s}", "a": "${item.x}"})
        assert result["a"].is_fragmented is False

    @pytest.mark.anyio
    async def test_split_stream_empty(self):
        stream = make_stream([])
        renderer = VariableRenderer(make_source_resolver({"s": stream}))
        result = await renderer.render({"|": "${s}", "a": "${item.x}"})
        assert await collect_async(result["a"]) == []
