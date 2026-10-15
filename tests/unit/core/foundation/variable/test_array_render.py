"""Semantic contract tests for ``ArrayValueRenderer.render``.

``ArrayValueRenderer`` is the generic counterpart of the media renderers.
Its matrix is the same shape; the per-element wrapper is also
``ArrayValue`` (there is no distinct inner wrapper type).

* ``item_is_list=False`` → each batch element is a scalar.
  - scalar + ``single_as_array`` → ``ArrayValue([a], is_single=True)``.
  - flat ``[a, b]`` → one ``ArrayValue([a, b])`` (unit).
  - nested ``[[a, b], [c]]`` → ``List[ArrayValue]`` (explicit batch).
* ``item_is_list=True`` → each batch element is a group.
  - scalar + lift / flat ``[a, b]`` + lift → one ``ArrayValue`` (unit).
  - nested ``[[a, b], [c]]`` → ``List[ArrayValue]`` (explicit batch of groups).
* ``single_as_array`` flips ``is_single=True`` on the unit when the input
  was NOT already explicitly batch-shaped. No outer wrapper is added —
  ``ArrayValue`` is always a unit elsewhere in the codebase.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.array import ArrayValue, ArrayValueRenderer


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def collect(value: Any) -> List[Any]:
    return [item async for item in value]


async def async_iter(items):
    for item in items:
        yield item


# ============================================================================
# item_is_list=False — element = scalar, outer = batch of scalars
# ============================================================================


class TestFlatBatch:
    @pytest.mark.anyio
    async def test_none_input_returns_none(self):
        result = await ArrayValueRenderer().render(None)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_without_lift_raises(self):
        """Scalar input without ``single_as_array`` is not an array — the
        renderer fails fast with a clear TypeError."""
        with pytest.raises(TypeError):
            await ArrayValueRenderer().render("x")

    @pytest.mark.anyio
    async def test_scalar_with_lift(self):
        result = await ArrayValueRenderer().render("x", single_as_array=True)

        assert isinstance(result, ArrayValue)
        assert result.is_single is True
        assert await collect(result) == ["x"]

    @pytest.mark.anyio
    async def test_flat_list_is_one_batch(self):
        result = await ArrayValueRenderer().render(["a", "b"])

        assert isinstance(result, ArrayValue)
        assert result.is_single is False
        assert await collect(result) == ["a", "b"]

    @pytest.mark.anyio
    async def test_flat_list_with_lift_keeps_is_single_false(self):
        result = await ArrayValueRenderer().render(["a", "b"], single_as_array=True)

        assert isinstance(result, ArrayValue)
        assert result.is_single is False

    @pytest.mark.anyio
    async def test_nested_list_is_batch_of_arrays(self):
        result = await ArrayValueRenderer().render([["a", "b"], ["c"]])

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, ArrayValue) for x in result)
        assert await collect(result[0]) == ["a", "b"]
        assert await collect(result[1]) == ["c"]

    @pytest.mark.anyio
    async def test_empty_list_is_empty_batch(self):
        result = await ArrayValueRenderer().render([])

        assert isinstance(result, ArrayValue)
        assert result.is_single is False
        assert await collect(result) == []


# ============================================================================
# item_is_list=True — element = group (ArrayValue), outer = batch of groups
# ============================================================================


class TestGroupedBatch:
    """``item_is_list=True``: each batch element is a group (``ArrayValue``).
    Non-batch inputs collapse to one ``ArrayValue`` (unit); batch inputs
    become a Python ``List[ArrayValue]``."""

    @pytest.mark.anyio
    async def test_none_input_returns_none(self):
        result = await ArrayValueRenderer().render(None, item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_without_lift_returns_none(self):
        result = await ArrayValueRenderer().render("x", item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_with_lift_is_list_of_one_group(self):
        result = await ArrayValueRenderer().render(
            "x", item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ArrayValue)
        assert result[0].is_single is True
        assert await collect(result[0]) == ["x"]

    @pytest.mark.anyio
    async def test_flat_list_without_lift_returns_none(self):
        result = await ArrayValueRenderer().render(["a", "b"], item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_flat_list_with_lift_is_list_of_one_group(self):
        result = await ArrayValueRenderer().render(
            ["a", "b"], item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ArrayValue)
        assert result[0].is_single is False
        assert await collect(result[0]) == ["a", "b"]

    @pytest.mark.anyio
    async def test_nested_list_is_list_of_groups(self):
        result = await ArrayValueRenderer().render(
            [["a", "b"], ["c"]], item_is_list=True
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(g, ArrayValue) for g in result)
        assert await collect(result[0]) == ["a", "b"]
        assert await collect(result[1]) == ["c"]

    @pytest.mark.anyio
    async def test_nested_list_with_lift_stays_a_list(self):
        result = await ArrayValueRenderer().render(
            [["a", "b"], ["c"]], item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 2


# ============================================================================
# Streaming inputs
# ============================================================================


class TestNonFragmentedStream:
    @pytest.mark.anyio
    async def test_flat_stream_of_scalars_without_lift_raises(self):
        """A non-fragmented stream of scalar inputs without ``single_as_array``
        is a contract violation — each per-chunk render raises TypeError."""
        source = StreamChunkIterator(async_iter(["a", "b"]))

        result = await ArrayValueRenderer().render(source)

        assert isinstance(result, StreamChunkIterator)
        with pytest.raises(TypeError):
            await collect(result)

    @pytest.mark.anyio
    async def test_flat_stream_with_lift_wraps_each_as_single_batch_item(self):
        source = StreamChunkIterator(async_iter(["a", "b"]))

        result = await ArrayValueRenderer().render(source, single_as_array=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(c, ArrayValue) for c in chunks)
        assert all(c.is_single is True for c in chunks)

    @pytest.mark.anyio
    async def test_grouped_stream_yields_rendered_groups(self):
        source = StreamChunkIterator(async_iter([["a", "b"], ["c"]]))

        result = await ArrayValueRenderer().render(source, item_is_list=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(ch, ArrayValue) for ch in chunks)
        assert await collect(chunks[0]) == ["a", "b"]
        assert await collect(chunks[1]) == ["c"]


class TestFragmentedStream:
    @pytest.mark.anyio
    async def test_fragmented_stream_is_one_batch_item(self):
        source = StreamChunkIterator(async_iter(["a", "b"]), is_fragmented=True)

        result = await ArrayValueRenderer().render(source)

        assert isinstance(result, ArrayValue)
        assert result.is_single is False
        assert await collect(result) == ["a", "b"]

    @pytest.mark.anyio
    async def test_fragmented_stream_item_is_list(self):
        """``item_is_list=True`` + fragmented → one-element ``[ArrayValue]``."""
        source = StreamChunkIterator(async_iter(["a", "b"]), is_fragmented=True)

        result = await ArrayValueRenderer().render(
            source, item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ArrayValue)
        assert await collect(result[0]) == ["a", "b"]


# ============================================================================
# ArrayValue passthrough
# ============================================================================


class TestArrayValuePassthrough:
    @pytest.mark.anyio
    async def test_passthrough_preserves_elements(self):
        source = ArrayValue(["a", "b"])

        result = await ArrayValueRenderer().render(source)

        assert isinstance(result, ArrayValue)
        assert await collect(result) == ["a", "b"]

    @pytest.mark.anyio
    async def test_passthrough_preserves_is_single(self):
        source = ArrayValue(["a"], is_single=True)

        result = await ArrayValueRenderer().render(source)

        assert isinstance(result, ArrayValue)
        assert result.is_single is True

    @pytest.mark.anyio
    async def test_list_of_array_values_is_batch(self):
        """``[ArrayValue, ArrayValue]`` must be detected as a nested batch,
        not treated as a flat list of refs."""
        source = [ArrayValue(["a", "b"]), ArrayValue(["c"])]

        result = await ArrayValueRenderer().render(source)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, ArrayValue) for x in result)
        assert await collect(result[0]) == ["a", "b"]
        assert await collect(result[1]) == ["c"]
