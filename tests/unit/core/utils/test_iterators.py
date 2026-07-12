"""Unit tests for ``mindor.core.utils.iterators``."""

from typing import AsyncIterator, List

import pytest

from mindor.core.utils.iterators import BatchSourceIterator, TextDecodeIterator
from mindor.core.foundation.streaming.iterators import StreamEncodingIterator, StreamChunkIterator
from mindor.core.foundation.streaming.iterators import StreamEncodingFormat


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _async_iter(items: list) -> AsyncIterator:
    for item in items:
        yield item


async def _collect(source) -> list:
    return [item async for item in source]


class TestBatchSourceIteratorWithList:
    @pytest.mark.anyio
    async def test_exact_batch_division(self):
        result = await _collect(BatchSourceIterator([1, 2, 3, 4], batch_size=2))
        assert result == [[1, 2], [3, 4]]

    @pytest.mark.anyio
    async def test_uneven_last_batch_is_short(self):
        result = await _collect(BatchSourceIterator([1, 2, 3, 4, 5], batch_size=2))
        assert result == [[1, 2], [3, 4], [5]]

    @pytest.mark.anyio
    async def test_single_huge_batch(self):
        result = await _collect(BatchSourceIterator([1, 2, 3], batch_size=10))
        assert result == [[1, 2, 3]]

    @pytest.mark.anyio
    async def test_empty_source_produces_no_batches(self):
        result = await _collect(BatchSourceIterator([], batch_size=2))
        assert result == []


class TestBatchSourceIteratorWithAsyncIterator:
    @pytest.mark.anyio
    async def test_async_iterator_batched(self):
        result = await _collect(BatchSourceIterator(_async_iter([1, 2, 3, 4, 5]), batch_size=3))
        assert result == [[1, 2, 3], [4, 5]]


class TestBatchSourceIteratorWithScalar:
    @pytest.mark.anyio
    async def test_scalar_yielded_as_single_item_batch(self):
        result = await _collect(BatchSourceIterator("hello", batch_size=10))
        assert result == [["hello"]]

    @pytest.mark.anyio
    async def test_int_scalar_yielded_as_single_item(self):
        result = await _collect(BatchSourceIterator(42, batch_size=10))
        assert result == [[42]]


class TestBatchSourceIteratorWithTupleZip:
    @pytest.mark.anyio
    async def test_two_lists_zipped_into_paired_batches(self):
        result = await _collect(BatchSourceIterator(([1, 2, 3], ["a", "b", "c"]), batch_size=2))
        # Each tick is a tuple of (batch_a, batch_b)
        assert result == [([1, 2], ["a", "b"]), ([3], ["c"])]

    @pytest.mark.anyio
    async def test_none_slot_is_broadcast_as_none(self):
        result = await _collect(BatchSourceIterator(([1, 2], None), batch_size=1))
        assert result == [([1], None), ([2], None)]

    @pytest.mark.anyio
    async def test_unequal_lengths_raise(self):
        with pytest.raises(ValueError, match="different lengths"):
            await _collect(BatchSourceIterator(([1, 2], ["a"]), batch_size=2))

    @pytest.mark.anyio
    async def test_all_scalars_yield_once(self):
        result = await _collect(BatchSourceIterator(("a", "b"), batch_size=1))
        assert result == [(["a"], ["b"])]


class TestBatchSourceIteratorWithTupleBroadcast:
    @pytest.mark.anyio
    async def test_scalar_broadcast_across_list(self):
        result = await _collect(BatchSourceIterator((["im1", "im2", "im3"], "describe"), batch_size=1))
        assert result == [
            (["im1"], ["describe"]),
            (["im2"], ["describe"]),
            (["im3"], ["describe"]),
        ]

    @pytest.mark.anyio
    async def test_scalar_broadcast_leading_slot(self):
        result = await _collect(BatchSourceIterator(("query", ["d1", "d2", "d3"]), batch_size=1))
        assert result == [
            (["query"], ["d1"]),
            (["query"], ["d2"]),
            (["query"], ["d3"]),
        ]

    @pytest.mark.anyio
    async def test_scalar_broadcast_batched(self):
        result = await _collect(BatchSourceIterator(("q", ["d1", "d2", "d3", "d4", "d5"]), batch_size=2))
        assert result == [
            (["q", "q"], ["d1", "d2"]),
            (["q", "q"], ["d3", "d4"]),
            (["q"], ["d5"]),
        ]

    @pytest.mark.anyio
    async def test_scalar_broadcast_across_async_iterator(self):
        result = await _collect(BatchSourceIterator(("q", _async_iter(["d1", "d2", "d3"])), batch_size=1))
        assert result == [
            (["q"], ["d1"]),
            (["q"], ["d2"]),
            (["q"], ["d3"]),
        ]

    @pytest.mark.anyio
    async def test_scalar_broadcast_across_stream_iterator(self):
        result = await _collect(BatchSourceIterator(("q", StreamChunkIterator(_async_iter(["d1", "d2"]))), batch_size=1))
        assert result == [
            (["q"], ["d1"]),
            (["q"], ["d2"]),
        ]

    @pytest.mark.anyio
    async def test_scalar_and_none_broadcast_together(self):
        result = await _collect(BatchSourceIterator((["a", "b"], None, "z"), batch_size=1))
        assert result == [
            (["a"], None, ["z"]),
            (["b"], None, ["z"]),
        ]

    @pytest.mark.anyio
    async def test_scalar_broadcast_stops_when_iterable_exhausts(self):
        result = await _collect(BatchSourceIterator(("q", []), batch_size=1))
        assert result == []


class TestStreamChunkIterator:
    @pytest.mark.anyio
    async def test_yields_non_none_chunks(self):
        chunks = await _collect(StreamChunkIterator(_async_iter(["a", "b", "c"])))
        assert chunks == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_skips_none_chunks(self):
        chunks = await _collect(StreamChunkIterator(_async_iter(["a", None, "b", None, "c"])))
        assert chunks == ["a", "b", "c"]


class TestStreamEncodingIteratorTextFormat:
    @pytest.mark.anyio
    async def test_single_str_chunk(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter(["hello"]), StreamEncodingFormat.TEXT))
        assert chunks == ["hello"]

    @pytest.mark.anyio
    async def test_non_str_chunk_stringified(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter([42]), StreamEncodingFormat.TEXT))
        assert chunks == ["42"]


class TestStreamEncodingIteratorJsonFormat:
    @pytest.mark.anyio
    async def test_dict_chunk_serialized(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter([{"key": "value"}]), StreamEncodingFormat.JSON))
        assert chunks == ['{"key": "value"}']

    @pytest.mark.anyio
    async def test_scalar_chunk_serialized(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter([42]), StreamEncodingFormat.JSON))
        assert chunks == ["42"]


class TestStreamEncodingIteratorNoneSkipping:
    @pytest.mark.anyio
    async def test_none_chunks_skipped(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter(["hello", None, "world"]), StreamEncodingFormat.TEXT))
        assert chunks == ["hello", "world"]


class TestStreamEncodingIteratorNoFormat:
    @pytest.mark.anyio
    async def test_str_chunk_passes_through(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter(["hello"]), None))
        assert chunks == ["hello"]

    @pytest.mark.anyio
    async def test_dict_chunk_falls_back_to_json(self):
        chunks = await _collect(StreamEncodingIterator(_async_iter([{"k": "v"}]), None))
        assert chunks == ['{"k": "v"}']


class TestTextDecodeIterator:
    @pytest.mark.anyio
    async def test_decodes_utf8_chunks(self):
        chunks = await _collect(TextDecodeIterator(_async_iter([b"hello", b" world"])))
        assert "".join(chunks) == "hello world"

    @pytest.mark.anyio
    async def test_passes_through_str_chunks(self):
        chunks = await _collect(TextDecodeIterator(_async_iter(["hello", " world"])))
        assert chunks == ["hello", " world"]

    @pytest.mark.anyio
    async def test_skips_none_chunks(self):
        chunks = await _collect(TextDecodeIterator(_async_iter([b"a", None, b"b"])))
        assert "".join(chunks) == "ab"

    @pytest.mark.anyio
    async def test_multibyte_split_across_chunk_boundary(self):
        # "한" in UTF-8 is 3 bytes: 0xED 0x95 0x9C — split it across two chunks
        # so a naive byte-by-byte decoder would emit U+FFFD.
        utf8 = "한".encode("utf-8")
        chunks = await _collect(TextDecodeIterator(_async_iter([utf8[:2], utf8[2:]])))
        assert "".join(chunks) == "한"

    @pytest.mark.anyio
    async def test_trailing_decoder_flush_emitted(self):
        # Force buffered bytes — the final flush should produce nothing extra here
        # but the chain must complete without raising.
        chunks = await _collect(TextDecodeIterator(_async_iter([b"ok"])))
        assert "".join(chunks) == "ok"
