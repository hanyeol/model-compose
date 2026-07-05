"""Unit tests for ``TaskOutputRenderer`` in ``mindor.core.controller.base``."""

from typing import AsyncIterator

import pytest

from mindor.core.controller.base import TaskOutputRenderer
from mindor.core.foundation.streaming.iterators import (
    StreamChunkIterator,
    StreamEncodingIterator,
    StreamEncodingFormat,
)
from mindor.core.foundation.streaming.resources import StreamResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def renderer() -> TaskOutputRenderer:
    return TaskOutputRenderer()


async def _async_iter(items: list) -> AsyncIterator:
    for item in items:
        yield item


class _DummyStreamResource(StreamResource):
    """Minimal StreamResource used only for identity/passthrough assertions."""

    def __init__(self):
        super().__init__(content_type=None, filename=None)

    async def close(self) -> None:
        pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        yield b""


class TestPassthroughValues:
    @pytest.mark.anyio
    async def test_none_is_returned_as_is(self, renderer: TaskOutputRenderer):
        assert await renderer.render(None) is None

    @pytest.mark.anyio
    async def test_int_is_returned_as_is(self, renderer: TaskOutputRenderer):
        assert await renderer.render(42) == 42

    @pytest.mark.anyio
    async def test_float_is_returned_as_is(self, renderer: TaskOutputRenderer):
        assert await renderer.render(3.14) == 3.14

    @pytest.mark.anyio
    async def test_bool_is_returned_as_is(self, renderer: TaskOutputRenderer):
        assert await renderer.render(True) is True

    @pytest.mark.anyio
    async def test_str_is_returned_as_is(self, renderer: TaskOutputRenderer):
        assert await renderer.render("hello") == "hello"

    @pytest.mark.anyio
    async def test_bytes_is_returned_as_is(self, renderer: TaskOutputRenderer):
        assert await renderer.render(b"payload") == b"payload"

    @pytest.mark.anyio
    async def test_bytearray_is_returned_as_is(self, renderer: TaskOutputRenderer):
        value = bytearray(b"payload")
        assert await renderer.render(value) is value

    @pytest.mark.anyio
    async def test_stream_resource_is_returned_as_is(self, renderer: TaskOutputRenderer):
        resource = _DummyStreamResource()
        assert await renderer.render(resource) is resource

    @pytest.mark.anyio
    async def test_unknown_type_is_returned_as_is(self, renderer: TaskOutputRenderer):
        sentinel = object()
        assert await renderer.render(sentinel) is sentinel


class TestContainerNormalization:
    @pytest.mark.anyio
    async def test_dict_preserves_keys_and_atomic_values(self, renderer: TaskOutputRenderer):
        result = await renderer.render({"a": 1, "b": "two", "c": None})
        assert result == {"a": 1, "b": "two", "c": None}

    @pytest.mark.anyio
    async def test_list_preserves_atomic_values(self, renderer: TaskOutputRenderer):
        assert await renderer.render([1, "two", None]) == [1, "two", None]

    @pytest.mark.anyio
    async def test_tuple_is_normalized_to_list(self, renderer: TaskOutputRenderer):
        result = await renderer.render((1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_nested_dict_and_list(self, renderer: TaskOutputRenderer):
        result = await renderer.render({"a": {"b": [1, 2, {"c": 3}]}})
        assert result == {"a": {"b": [1, 2, {"c": 3}]}}

    @pytest.mark.anyio
    async def test_nested_tuple_becomes_list(self, renderer: TaskOutputRenderer):
        result = await renderer.render([1, (2, 3), [4, (5, 6)]])
        assert result == [1, [2, 3], [4, [5, 6]]]


class TestIteratorCollect:
    @pytest.mark.anyio
    async def test_fragmented_string_stream_is_joined_into_string(self, renderer: TaskOutputRenderer):
        source = StreamChunkIterator(_async_iter(["Hel", "lo, ", "world", "!"]), is_fragmented=True)
        result = await renderer.render({"text": source})
        assert result == {"text": "Hello, world!"}

    @pytest.mark.anyio
    async def test_fragmented_bytes_stream_is_joined_into_bytes(self, renderer: TaskOutputRenderer):
        source = StreamChunkIterator(_async_iter([b"foo", b"bar", b"baz"]), is_fragmented=True)
        result = await renderer.render({"blob": source})
        assert result == {"blob": b"foobarbaz"}

    @pytest.mark.anyio
    async def test_element_string_stream_is_collected_as_list(self, renderer: TaskOutputRenderer):
        source = StreamChunkIterator(_async_iter(["line1\n", "line2\n"]), is_fragmented=False)
        result = await renderer.render({"lines": source})
        assert result == {"lines": ["line1\n", "line2\n"]}

    @pytest.mark.anyio
    async def test_element_dict_stream_is_collected_as_list(self, renderer: TaskOutputRenderer):
        source = StreamChunkIterator(
            _async_iter([{"i": 0}, {"i": 1}]), is_fragmented=False
        )
        result = await renderer.render({"items": source})
        assert result == {"items": [{"i": 0}, {"i": 1}]}

    @pytest.mark.anyio
    async def test_bare_async_iterator_is_collected_as_list(self, renderer: TaskOutputRenderer):
        result = await renderer.render({"chunks": _async_iter(["a", "b", "c"])})
        assert result == {"chunks": ["a", "b", "c"]}

    @pytest.mark.anyio
    async def test_stream_encoding_iterator_is_collected_as_list(self, renderer: TaskOutputRenderer):
        # StreamEncodingIterator has no is_fragmented flag → treated as element stream.
        source = StreamEncodingIterator(
            _async_iter([{"k": 1}, {"k": 2}]), format=StreamEncodingFormat.JSON
        )
        result = await renderer.render({"events": source})
        # JSON format encodes each chunk into a JSON string.
        assert result == {"events": ['{"k": 1}', '{"k": 2}']}

    @pytest.mark.anyio
    async def test_empty_fragmented_stream_returns_empty_string(self, renderer: TaskOutputRenderer):
        # When is_fragmented=True and chunks are all str (vacuously true for []),
        # join returns "".
        source = StreamChunkIterator(_async_iter([]), is_fragmented=True)
        result = await renderer.render({"text": source})
        assert result == {"text": ""}

    @pytest.mark.anyio
    async def test_empty_element_stream_returns_empty_list(self, renderer: TaskOutputRenderer):
        source = StreamChunkIterator(_async_iter([]), is_fragmented=False)
        result = await renderer.render({"items": source})
        assert result == {"items": []}

    @pytest.mark.anyio
    async def test_fragmented_mixed_chunks_fall_back_to_list(self, renderer: TaskOutputRenderer):
        # is_fragmented=True but chunks are neither uniformly str nor uniformly bytes.
        source = StreamChunkIterator(_async_iter(["a", 1, b"c"]), is_fragmented=True)
        result = await renderer.render({"mixed": source})
        assert result == {"mixed": ["a", 1, b"c"]}

    @pytest.mark.anyio
    async def test_top_level_iterator_is_passed_through(self, renderer: TaskOutputRenderer):
        # Top-level iterator is passed through so that streaming consumers
        # (HTTP SSE, WebUI, ...) can iterate the chunks in real time.
        source = StreamChunkIterator(_async_iter(["a", "b"]), is_fragmented=True)
        result = await renderer.render(source)
        assert result is source


class TestMixedShapes:
    @pytest.mark.anyio
    async def test_dict_with_iterator_and_atomic_values(self, renderer: TaskOutputRenderer):
        result = await renderer.render(
            {
                "transcript": StreamChunkIterator(
                    _async_iter(["Hel", "lo"]), is_fragmented=True
                ),
                "duration": 1.5,
                "meta": {"source": "test"},
            }
        )
        assert result == {
            "transcript": "Hello",
            "duration": 1.5,
            "meta": {"source": "test"},
        }

    @pytest.mark.anyio
    async def test_list_with_multiple_iterators(self, renderer: TaskOutputRenderer):
        result = await renderer.render(
            [
                StreamChunkIterator(_async_iter(["a", "b"]), is_fragmented=True),
                StreamChunkIterator(_async_iter(["c", "d"]), is_fragmented=False),
            ]
        )
        assert result == ["ab", ["c", "d"]]

    @pytest.mark.anyio
    async def test_deeply_nested_iterator_leaf_is_collected(self, renderer: TaskOutputRenderer):
        source = StreamChunkIterator(_async_iter(["x", "y"]), is_fragmented=True)
        result = await renderer.render({"outer": {"inner": [source]}})
        assert result == {"outer": {"inner": ["xy"]}}

    @pytest.mark.anyio
    async def test_stream_resource_leaf_is_preserved(self, renderer: TaskOutputRenderer):
        resource = _DummyStreamResource()
        result = await renderer.render({"file": resource, "name": "x.bin"})
        assert result["file"] is resource
        assert result["name"] == "x.bin"
