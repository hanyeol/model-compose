"""Unit tests for ``mindor.core.utils.iterators``."""

from typing import AsyncIterator, List

import pytest

from mindor.core.utils.iterators import BatchSourceIterator, TextDecodeIterator
from mindor.core.utils.streaming.iterators import EventStreamIterator, StreamChunkIterator
from mindor.core.utils.streaming.iterators import EventStreamFormat


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


class TestStreamChunkIterator:
    @pytest.mark.anyio
    async def test_yields_non_none_chunks(self):
        chunks = await _collect(StreamChunkIterator(_async_iter(["a", "b", "c"])))
        assert chunks == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_skips_none_chunks(self):
        chunks = await _collect(StreamChunkIterator(_async_iter(["a", None, "b", None, "c"])))
        assert chunks == ["a", "b", "c"]


class TestEventStreamIteratorTextFormat:
    @pytest.mark.anyio
    async def test_single_str_chunk(self):
        chunks = await _collect(EventStreamIterator(_async_iter(["hello"]), EventStreamFormat.TEXT))
        assert chunks == ["hello"]

    @pytest.mark.anyio
    async def test_non_str_chunk_stringified(self):
        chunks = await _collect(EventStreamIterator(_async_iter([42]), EventStreamFormat.TEXT))
        assert chunks == ["42"]


class TestEventStreamIteratorJsonFormat:
    @pytest.mark.anyio
    async def test_dict_chunk_serialized(self):
        chunks = await _collect(EventStreamIterator(_async_iter([{"key": "value"}]), EventStreamFormat.JSON))
        assert chunks == ['{"key": "value"}']

    @pytest.mark.anyio
    async def test_scalar_chunk_serialized(self):
        chunks = await _collect(EventStreamIterator(_async_iter([42]), EventStreamFormat.JSON))
        assert chunks == ["42"]


class TestEventStreamIteratorNoneSkipping:
    @pytest.mark.anyio
    async def test_none_chunks_skipped(self):
        chunks = await _collect(EventStreamIterator(_async_iter(["hello", None, "world"]), EventStreamFormat.TEXT))
        assert chunks == ["hello", "world"]


class TestEventStreamIteratorNoFormat:
    @pytest.mark.anyio
    async def test_str_chunk_passes_through(self):
        chunks = await _collect(EventStreamIterator(_async_iter(["hello"]), None))
        assert chunks == ["hello"]

    @pytest.mark.anyio
    async def test_dict_chunk_falls_back_to_json(self):
        chunks = await _collect(EventStreamIterator(_async_iter([{"k": "v"}]), None))
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
