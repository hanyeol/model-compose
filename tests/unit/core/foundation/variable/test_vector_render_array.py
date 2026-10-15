"""Semantic contract tests for ``VectorValueRenderer.render_array``.

Vectors sit one axis deeper than scalars: a single "element" to this
renderer is already a 1-D ``List[float]``. The matrix is shifted by one
axis compared to the media renderers:

- ``item_is_list=False``: one batch element is one vector (``List[float]``).
  - 1-D ``[1.0, 2.0]`` is a scalar input → ``None`` without lift,
    ``VectorArrayValue([v], is_single=True)`` with lift.
  - 2-D ``[[...], [...]]`` → one ``VectorArrayValue`` (unit = batch of
    vectors).
  - 3-D ``[[[...]], [[...]]]`` → ``List[VectorArrayValue]`` (explicit batch).
- ``item_is_list=True``: one batch element is a group of vectors.
  - scalar + lift → one ``VectorArrayValue`` (unit = one group of one).
  - 2-D + lift → one ``VectorArrayValue`` (unit = one group of N).
  - 3-D → ``List[VectorArrayValue]`` (explicit batch of groups).
- ``single_as_array=True`` flips ``is_single=True`` on the unit when the
  input was NOT already explicitly batch-shaped. No outer wrapper is
  added — ``VectorArrayValue`` is always a unit.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.vector import (
    VectorArrayValue,
    VectorValue,
    VectorValueRenderer,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def collect(value: Any) -> List[Any]:
    return [item async for item in value]


async def async_iter(items):
    for item in items:
        yield item


def vec(*values: float) -> List[float]:
    return list(values)


# ============================================================================
# item_is_list=False — one batch element = one vector
# ============================================================================


class TestFlatBatch:
    @pytest.mark.anyio
    async def test_none_input_returns_none(self):
        result = await VectorValueRenderer().render_array(None)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_vector_without_lift_raises(self):
        """A 1-D list is one vector (scalar input) — without
        ``single_as_array`` the renderer fails fast with a clear TypeError."""
        with pytest.raises(TypeError):
            await VectorValueRenderer().render_array(vec(1.0, 2.0))

    @pytest.mark.anyio
    async def test_scalar_vector_with_lift(self):
        result = await VectorValueRenderer().render_array(vec(1.0, 2.0), single_as_array=True)

        assert isinstance(result, VectorArrayValue)
        assert result.is_single is True

        collected = await collect(result)
        assert len(collected) == 1
        assert isinstance(collected[0], VectorValue)
        assert collected[0].values == [1.0, 2.0]

    @pytest.mark.anyio
    async def test_flat_batch_is_one_batch_of_vectors(self):
        """2-D ``[[a], [b]]`` is a batch of two vectors."""
        result = await VectorValueRenderer().render_array([vec(1.0, 2.0), vec(3.0, 4.0)])

        assert isinstance(result, VectorArrayValue)
        assert result.is_single is False

        collected = await collect(result)
        assert len(collected) == 2
        assert collected[0].values == [1.0, 2.0]
        assert collected[1].values == [3.0, 4.0]

    @pytest.mark.anyio
    async def test_flat_batch_with_lift_keeps_is_single_false(self):
        result = await VectorValueRenderer().render_array(
            [vec(1.0, 2.0), vec(3.0, 4.0)], single_as_array=True
        )

        assert isinstance(result, VectorArrayValue)
        assert result.is_single is False

    @pytest.mark.anyio
    async def test_nested_batch_is_batch_of_vector_arrays(self):
        """3-D ``[[[...]], [[...]]]`` is batch of VectorArrayValue."""
        result = await VectorValueRenderer().render_array(
            [[vec(1.0, 2.0), vec(3.0, 4.0)], [vec(5.0, 6.0)]]
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, VectorArrayValue) for x in result)

        first = await collect(result[0])
        assert len(first) == 2
        assert first[0].values == [1.0, 2.0]

        second = await collect(result[1])
        assert len(second) == 1
        assert second[0].values == [5.0, 6.0]


# ============================================================================
# item_is_list=True — one batch element = one group (VectorArrayValue)
# ============================================================================


class TestGroupedBatch:
    @pytest.mark.anyio
    async def test_none_input_returns_none(self):
        result = await VectorValueRenderer().render_array(None, item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_vector_without_lift_returns_none(self):
        result = await VectorValueRenderer().render_array(
            vec(1.0, 2.0), item_is_list=True
        )
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_vector_with_lift_is_list_of_one_group(self):
        """Scalar vector + lift → one-element list containing one group."""
        result = await VectorValueRenderer().render_array(
            vec(1.0, 2.0), item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], VectorArrayValue)
        assert result[0].is_single is True

        vectors = await collect(result[0])
        assert len(vectors) == 1
        assert vectors[0].values == [1.0, 2.0]

    @pytest.mark.anyio
    async def test_flat_batch_without_lift_returns_none(self):
        """2-D is one group under item_is_list=True. Without lift, no batch."""
        result = await VectorValueRenderer().render_array(
            [vec(1.0, 2.0), vec(3.0, 4.0)], item_is_list=True
        )
        assert result is None

    @pytest.mark.anyio
    async def test_flat_batch_with_lift_is_list_of_one_group(self):
        """2-D + lift → one-element list containing one group of both vectors."""
        result = await VectorValueRenderer().render_array(
            [vec(1.0, 2.0), vec(3.0, 4.0)],
            item_is_list=True,
            single_as_array=True,
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], VectorArrayValue)
        assert result[0].is_single is False

        vectors = await collect(result[0])
        assert len(vectors) == 2
        assert vectors[0].values == [1.0, 2.0]
        assert vectors[1].values == [3.0, 4.0]

    @pytest.mark.anyio
    async def test_nested_batch_is_list_of_groups(self):
        """3-D ``[[[v1], [v2]], [[v3]]]`` → ``List[VectorArrayValue]``."""
        result = await VectorValueRenderer().render_array(
            [[vec(1.0, 2.0), vec(3.0, 4.0)], [vec(5.0, 6.0)]],
            item_is_list=True,
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(g, VectorArrayValue) for g in result)
        assert len(await collect(result[0])) == 2
        assert len(await collect(result[1])) == 1

    @pytest.mark.anyio
    async def test_nested_batch_with_lift_stays_a_list(self):
        result = await VectorValueRenderer().render_array(
            [[vec(1.0, 2.0), vec(3.0, 4.0)], [vec(5.0, 6.0)]],
            item_is_list=True,
            single_as_array=True,
        )

        assert isinstance(result, list)
        assert len(result) == 2


# ============================================================================
# Streaming
# ============================================================================


class TestNonFragmentedStream:
    """Vectors share the stream model with other renderers: a non-fragmented
    ``StreamChunkIterator`` is a batch stream of per-item inputs. Each chunk
    goes through the same per-item path as a materialized input."""

    @pytest.mark.anyio
    async def test_flat_stream_wraps_each_vector_as_single_batch_item(self):
        """``item_is_list=False`` + ``single_as_array=True``: each vector chunk
        becomes a one-vector ``VectorArrayValue`` with ``is_single=True``."""
        source = StreamChunkIterator(async_iter([vec(1.0), vec(2.0)]))

        result = await VectorValueRenderer().render_array(source, single_as_array=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(c, VectorArrayValue) for c in chunks)
        assert all(c.is_single is True for c in chunks)

    @pytest.mark.anyio
    async def test_grouped_stream_yields_rendered_groups(self):
        source = StreamChunkIterator(
            async_iter([[vec(1.0), vec(2.0)], [vec(3.0)]])
        )

        result = await VectorValueRenderer().render_array(source, item_is_list=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(ch, VectorArrayValue) for ch in chunks)
        assert len(await collect(chunks[0])) == 2
        assert len(await collect(chunks[1])) == 1


class TestFragmentedStream:
    """A fragmented ``StreamChunkIterator`` represents one logical vector
    array delivered in pieces — one batch element only. Each piece is a
    single vector (``List[float]`` or ``VectorValue``)."""

    @pytest.mark.anyio
    async def test_fragmented_stream_is_one_batch_item(self):
        source = StreamChunkIterator(
            async_iter([vec(1.0), vec(2.0)]), is_fragmented=True
        )

        result = await VectorValueRenderer().render_array(source)

        assert isinstance(result, VectorArrayValue)
        assert result.is_single is False

        collected = await collect(result)
        assert len(collected) == 2
        assert collected[0].values == [1.0]
        assert collected[1].values == [2.0]

    @pytest.mark.anyio
    async def test_fragmented_stream_item_is_list(self):
        """``item_is_list=True`` + fragmented: the whole stream is one group,
        returned as a one-element ``[VectorArrayValue]``."""
        source = StreamChunkIterator(
            async_iter([vec(1.0), vec(2.0)]), is_fragmented=True
        )

        result = await VectorValueRenderer().render_array(
            source, item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], VectorArrayValue)

        vectors = await collect(result[0])
        assert len(vectors) == 2
        assert vectors[0].values == [1.0]

    @pytest.mark.anyio
    async def test_nested_batch_of_fragmented_streams(self):
        """``[frag_stream, frag_stream]`` with ``item_is_list=False``: each
        element is a per-item vector array delivered in pieces. Result is
        ``List[VectorArrayValue]`` — one entry per fragmented stream."""
        s1 = StreamChunkIterator(async_iter([vec(1.0), vec(2.0)]), is_fragmented=True)
        s2 = StreamChunkIterator(async_iter([vec(3.0)]), is_fragmented=True)

        result = await VectorValueRenderer().render_array([s1, s2])

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, VectorArrayValue) for x in result)
        assert len(await collect(result[0])) == 2
        assert len(await collect(result[1])) == 1


# ============================================================================
# VectorArrayValue passthrough
# ============================================================================


class TestVectorArrayValuePassthrough:
    @pytest.mark.anyio
    async def test_passthrough_preserves_elements(self):
        source = VectorArrayValue([VectorValue([1.0]), VectorValue([2.0])])

        result = await VectorValueRenderer().render_array(source)

        assert isinstance(result, VectorArrayValue)
        collected = await collect(result)
        assert len(collected) == 2
        assert collected[0].values == [1.0]
        assert collected[1].values == [2.0]

    @pytest.mark.anyio
    async def test_passthrough_preserves_is_single(self):
        source = VectorArrayValue([VectorValue([1.0])], is_single=True)

        result = await VectorValueRenderer().render_array(source)

        assert isinstance(result, VectorArrayValue)
        assert result.is_single is True

    @pytest.mark.anyio
    async def test_list_of_vector_array_values_is_batch(self):
        """``[VectorArrayValue, VectorArrayValue]`` must be detected as a
        nested batch, not treated as a 2-D vector array."""
        source = [
            VectorArrayValue([VectorValue([1.0]), VectorValue([2.0])]),
            VectorArrayValue([VectorValue([3.0])]),
        ]

        result = await VectorValueRenderer().render_array(source)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, VectorArrayValue) for x in result)
        assert len(await collect(result[0])) == 2
        assert len(await collect(result[1])) == 1
