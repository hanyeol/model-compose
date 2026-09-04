"""Tests for `_render_zip` (`&`) — static, streaming, and nested combinations.

`&` zips several sources element-wise into a stream/list of dicts keyed by the
input keys. Semantics:
- shortest wins (stops when any source is exhausted)
- if any source is None, result is `[]`
- if any source is a stream, result is a StreamChunkIterator, otherwise a list
- `is_fragmented` is propagated from stream sources
"""

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
# `&` (zip) — static inputs
# ============================================================

class TestZipStatic:
    """Zip operator over materialized lists."""

    @pytest.mark.anyio
    async def test_two_lists_same_length(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": [1, 2, 3],
            "b": ["x", "y", "z"],
        }))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert result == [
            {"num": 1, "letter": "x"},
            {"num": 2, "letter": "y"},
            {"num": 3, "letter": "z"},
        ]

    @pytest.mark.anyio
    async def test_shortest_wins_left_shorter(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": [1, 2],
            "b": ["x", "y", "z", "w"],
        }))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert result == [
            {"num": 1, "letter": "x"},
            {"num": 2, "letter": "y"},
        ]

    @pytest.mark.anyio
    async def test_shortest_wins_right_shorter(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": [1, 2, 3, 4],
            "b": ["x"],
        }))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert result == [{"num": 1, "letter": "x"}]

    @pytest.mark.anyio
    async def test_three_sources(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": [1, 2],
            "b": ["x", "y"],
            "c": [True, False],
        }))
        result = await renderer.render({"&": {
            "num": "${a}", "letter": "${b}", "flag": "${c}",
        }})
        assert result == [
            {"num": 1, "letter": "x", "flag": True},
            {"num": 2, "letter": "y", "flag": False},
        ]

    @pytest.mark.anyio
    async def test_empty_source_produces_empty_result(self):
        renderer = VariableRenderer(make_source_resolver({
            "a": [],
            "b": [1, 2, 3],
        }))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert result == []

    @pytest.mark.anyio
    async def test_none_source_returns_empty_list(self):
        """Consistent with `*` (map): a None source means nothing to iterate."""
        renderer = VariableRenderer(make_source_resolver({
            "a": None,
            "b": [1, 2],
        }))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert result == []

    @pytest.mark.anyio
    async def test_all_none_returns_empty_list(self):
        renderer = VariableRenderer(make_source_resolver({"a": None, "b": None}))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert result == []

    @pytest.mark.anyio
    async def test_single_source(self):
        """Zipping a single source is degenerate but should still work: one
        dict per element, keyed by the given name."""
        renderer = VariableRenderer(make_source_resolver({"a": [10, 20, 30]}))
        result = await renderer.render({"&": {"only": "${a}"}})
        assert result == [{"only": 10}, {"only": 20}, {"only": 30}]

    @pytest.mark.anyio
    async def test_zips_dict_elements(self):
        """Zip should preserve element identity (dicts pass through unchanged)."""
        renderer = VariableRenderer(make_source_resolver({
            "frames": [{"number": 1, "image": "img1"}, {"number": 2, "image": "img2"}],
            "regions": [[{"bbox": "A"}], []],
        }))
        result = await renderer.render({"&": {
            "frame": "${frames}",
            "regions": "${regions}",
        }})
        assert result == [
            {"frame": {"number": 1, "image": "img1"}, "regions": [{"bbox": "A"}]},
            {"frame": {"number": 2, "image": "img2"}, "regions": []},
        ]


# ============================================================
# `&` (zip) — invalid inputs
# ============================================================

class TestZipInvalid:
    """Zip operator rejects malformed configurations."""

    @pytest.mark.anyio
    async def test_empty_dict_raises(self):
        renderer = VariableRenderer(make_source_resolver({}))
        with pytest.raises(ValueError, match="non-empty dict"):
            await renderer.render({"&": {}})

    @pytest.mark.anyio
    async def test_list_argument_raises(self):
        """`&` requires a dict argument; a list is ambiguous (no output keys)."""
        renderer = VariableRenderer(make_source_resolver({"a": [1], "b": [2]}))
        with pytest.raises(TypeError, match="must resolve to a dict"):
            await renderer.render({"&": ["${a}", "${b}"]})

    @pytest.mark.anyio
    async def test_scalar_argument_raises(self):
        renderer = VariableRenderer(make_source_resolver({"a": [1]}))
        with pytest.raises(TypeError, match="must resolve to a dict"):
            await renderer.render({"&": "${a}"})

    @pytest.mark.anyio
    async def test_variable_resolving_to_dict_is_accepted(self):
        """A single variable that resolves to a dict is treated the same as a literal dict."""
        renderer = VariableRenderer(make_source_resolver({
            "sources": {"num": [1, 2], "letter": ["a", "b"]},
        }))
        result = await renderer.render({"&": "${sources}"})
        assert result == [{"num": 1, "letter": "a"}, {"num": 2, "letter": "b"}]

    @pytest.mark.anyio
    async def test_none_source_returns_none(self):
        """A source variable that resolves to None short-circuits to None (matches `+`)."""
        renderer = VariableRenderer(make_source_resolver({"missing": None}))
        result = await renderer.render({"&": "${missing}"})
        assert result is None


# ============================================================
# `&` (zip) — streaming inputs
# ============================================================

class TestZipStream:
    """Zip operator with stream inputs."""

    @pytest.mark.anyio
    async def test_two_streams_same_length(self):
        stream_a = make_stream([1, 2, 3])
        stream_b = make_stream(["x", "y", "z"])
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == [
            {"num": 1, "letter": "x"},
            {"num": 2, "letter": "y"},
            {"num": 3, "letter": "z"},
        ]

    @pytest.mark.anyio
    async def test_stream_shortest_left(self):
        stream_a = make_stream([1, 2])
        stream_b = make_stream(["x", "y", "z", "w"])
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert await collect_async(result) == [
            {"num": 1, "letter": "x"},
            {"num": 2, "letter": "y"},
        ]

    @pytest.mark.anyio
    async def test_stream_shortest_right(self):
        stream_a = make_stream([1, 2, 3])
        stream_b = make_stream(["x"])
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert await collect_async(result) == [{"num": 1, "letter": "x"}]

    @pytest.mark.anyio
    async def test_stream_mixed_with_list(self):
        stream_a = make_stream([1, 2, 3])
        renderer = VariableRenderer(make_source_resolver({
            "a": stream_a,
            "b": ["x", "y", "z"],
        }))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert isinstance(result, StreamChunkIterator)
        assert await collect_async(result) == [
            {"num": 1, "letter": "x"},
            {"num": 2, "letter": "y"},
            {"num": 3, "letter": "z"},
        ]

    @pytest.mark.anyio
    async def test_stream_mixed_with_shorter_list_stops(self):
        stream_a = make_stream([1, 2, 3, 4, 5])
        renderer = VariableRenderer(make_source_resolver({
            "a": stream_a,
            "b": ["x", "y"],
        }))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})
        assert await collect_async(result) == [
            {"num": 1, "letter": "x"},
            {"num": 2, "letter": "y"},
        ]

    @pytest.mark.anyio
    async def test_empty_stream_produces_empty_result(self):
        stream_a = make_stream([])
        renderer = VariableRenderer(make_source_resolver({
            "a": stream_a,
            "b": [1, 2, 3],
        }))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert await collect_async(result) == []

    @pytest.mark.anyio
    async def test_is_fragmented_true_when_any_source_fragmented(self):
        stream_a = make_stream([1, 2], is_fragmented=True)
        stream_b = make_stream(["x", "y"], is_fragmented=False)
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is True

    @pytest.mark.anyio
    async def test_is_fragmented_false_when_all_sources_non_fragmented(self):
        stream_a = make_stream([1, 2], is_fragmented=False)
        stream_b = make_stream(["x", "y"], is_fragmented=False)
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert isinstance(result, StreamChunkIterator)
        assert result.is_fragmented is False

    @pytest.mark.anyio
    async def test_list_only_result_is_not_a_stream(self):
        """Purely static sources must NOT be wrapped in a StreamChunkIterator."""
        renderer = VariableRenderer(make_source_resolver({"a": [1, 2], "b": ["x", "y"]}))
        result = await renderer.render({"&": {"a": "${a}", "b": "${b}"}})
        assert isinstance(result, list)


# ============================================================
# `&` (zip) — laziness / ordering
# ============================================================

class TestZipLaziness:
    """Streaming zip must consume sources lazily and in lockstep."""

    @pytest.mark.anyio
    async def test_stops_before_draining_longer_stream(self):
        """After the short source ends, the long source must not be fully
        drained — we should only have pulled as many items as we yielded."""
        pulled_from_b = []

        async def slow_b():
            for value in ["x", "y", "z", "w", "u"]:
                pulled_from_b.append(value)
                yield value

        stream_a = make_stream([1, 2])
        stream_b = StreamChunkIterator(slow_b(), is_fragmented=True)
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"num": "${a}", "letter": "${b}"}})

        collected = await collect_async(result)
        assert collected == [{"num": 1, "letter": "x"}, {"num": 2, "letter": "y"}]
        # After yielding 2 rows, `a` is exhausted on the 3rd probe, so we must
        # have advanced `b` at most twice — the 3rd advance never happens.
        assert pulled_from_b == ["x", "y"]

    @pytest.mark.anyio
    async def test_preserves_source_key_order(self):
        """Output dict should keep the key order from the `&` spec so
        downstream `${item.first}` / `${item.second}` lookups are stable."""
        stream_a = make_stream([1])
        stream_b = make_stream([2])
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {"second": "${b}", "first": "${a}"}})
        row = (await collect_async(result))[0]
        assert list(row.keys()) == ["second", "first"]


# ============================================================
# `&` combined with other operators
# ============================================================

class TestZipCompositions:
    """Zip composed with `*` (map) and `+` (join)."""

    @pytest.mark.anyio
    async def test_map_over_zipped_stream(self):
        """`*` over a zipped stream should let templates reference the
        zipped dict via `${item.<key>}`. `*` with a dict value expects
        `{input: ..., where: ...}` — nest the `&` under `input`."""
        stream_a = make_stream([1, 2, 3])
        stream_b = make_stream(["x", "y", "z"])
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({
            "*": {"input": {"&": {"num": "${a}", "letter": "${b}"}}},
            "label": "${item.letter}-${item.num}",
        })
        assert await collect_async(result) == [
            {"label": "x-1"},
            {"label": "y-2"},
            {"label": "z-3"},
        ]

    @pytest.mark.anyio
    async def test_zip_of_mapped_streams(self):
        """Two `*`-mapped streams should be zippable element-wise."""
        stream_a = make_stream([1, 2, 3])
        stream_b = make_stream([10, 20, 30])
        renderer = VariableRenderer(make_source_resolver({"a": stream_a, "b": stream_b}))
        result = await renderer.render({"&": {
            "left":  {"*": "${a}"},
            "right": {"*": "${b}"},
        }})
        assert await collect_async(result) == [
            {"left": 1, "right": 10},
            {"left": 2, "right": 20},
            {"left": 3, "right": 30},
        ]
