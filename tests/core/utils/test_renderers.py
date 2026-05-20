"""Tests for VariableRenderer type conversions, SSE wrapping, and spread operations."""

import base64
import io
from collections.abc import AsyncIterator

import pytest
from starlette.datastructures import UploadFile

from mindor.core.utils.renderers import VariableRenderer
from mindor.core.utils.streaming import (
    BytesStreamResource,
    EventIteratorStreamResource,
    StreamFormat,
)


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# ---- Helpers ----

def make_source_resolver(sources):
    """Create a source resolver that returns values from a dict."""
    async def resolver(key, index=None):
        value = sources.get(key)
        if index is not None and isinstance(value, list):
            return value[index]
        return value
    return resolver


async def make_async_iterator(items):
    """Create an AsyncIterator from a list."""
    for item in items:
        yield item


async def collect_async(iterator):
    """Collect all items from an async iterator."""
    return [item async for item in iterator]


# ============================
# number conversion
# ============================

class TestConvertNumber:
    """Test 'as number' type conversion."""

    @pytest.mark.anyio
    async def test_string_to_float(self):
        """Test that a numeric string is converted to float."""
        renderer = VariableRenderer(make_source_resolver({"v": "3.14"}))
        result = await renderer.render("${v as number}")
        assert result == 3.14
        assert isinstance(result, float)

    @pytest.mark.anyio
    async def test_int_to_float(self):
        """Test that an integer is converted to float."""
        renderer = VariableRenderer(make_source_resolver({"v": 42}))
        result = await renderer.render("${v as number}")
        assert result == 42.0
        assert isinstance(result, float)

    @pytest.mark.anyio
    async def test_float_passthrough(self):
        """Test that a float value passes through unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": 2.718}))
        result = await renderer.render("${v as number}")
        assert result == 2.718

    @pytest.mark.anyio
    async def test_negative_number(self):
        """Test that a negative numeric string is converted correctly."""
        renderer = VariableRenderer(make_source_resolver({"v": "-1.5"}))
        result = await renderer.render("${v as number}")
        assert result == -1.5

    @pytest.mark.anyio
    async def test_zero(self):
        """Test that zero string is converted to 0.0."""
        renderer = VariableRenderer(make_source_resolver({"v": "0"}))
        result = await renderer.render("${v as number}")
        assert result == 0.0


# ============================
# integer conversion
# ============================

class TestConvertInteger:
    """Test 'as integer' type conversion."""

    @pytest.mark.anyio
    async def test_string_to_int(self):
        """Test that a numeric string is converted to int."""
        renderer = VariableRenderer(make_source_resolver({"v": "42"}))
        result = await renderer.render("${v as integer}")
        assert result == 42
        assert isinstance(result, int)

    @pytest.mark.anyio
    async def test_float_to_int(self):
        """Test that a float is truncated to int."""
        renderer = VariableRenderer(make_source_resolver({"v": 3.9}))
        result = await renderer.render("${v as integer}")
        assert result == 3

    @pytest.mark.anyio
    async def test_negative_int(self):
        """Test that a negative string is converted to negative int."""
        renderer = VariableRenderer(make_source_resolver({"v": "-7"}))
        result = await renderer.render("${v as integer}")
        assert result == -7

    @pytest.mark.anyio
    async def test_zero(self):
        """Test that zero string is converted to 0."""
        renderer = VariableRenderer(make_source_resolver({"v": "0"}))
        result = await renderer.render("${v as integer}")
        assert result == 0


# ============================
# boolean conversion
# ============================

class TestConvertBoolean:
    """Test 'as boolean' type conversion."""

    @pytest.mark.anyio
    async def test_true_string(self):
        """Test that 'true' string converts to True."""
        renderer = VariableRenderer(make_source_resolver({"v": "true"}))
        result = await renderer.render("${v as boolean}")
        assert result is True

    @pytest.mark.anyio
    async def test_True_string(self):
        """Test that 'True' string converts to True."""
        renderer = VariableRenderer(make_source_resolver({"v": "True"}))
        result = await renderer.render("${v as boolean}")
        assert result is True

    @pytest.mark.anyio
    async def test_one_string(self):
        """Test that '1' string converts to True."""
        renderer = VariableRenderer(make_source_resolver({"v": "1"}))
        result = await renderer.render("${v as boolean}")
        assert result is True

    @pytest.mark.anyio
    async def test_false_string(self):
        """Test that 'false' string converts to False."""
        renderer = VariableRenderer(make_source_resolver({"v": "false"}))
        result = await renderer.render("${v as boolean}")
        assert result is False

    @pytest.mark.anyio
    async def test_zero_string(self):
        """Test that '0' string converts to False."""
        renderer = VariableRenderer(make_source_resolver({"v": "0"}))
        result = await renderer.render("${v as boolean}")
        assert result is False

    @pytest.mark.anyio
    async def test_arbitrary_string_is_false(self):
        """Test that an arbitrary string converts to False."""
        renderer = VariableRenderer(make_source_resolver({"v": "hello"}))
        result = await renderer.render("${v as boolean}")
        assert result is False

    @pytest.mark.anyio
    async def test_int_one(self):
        """Test that integer 1 converts to True."""
        renderer = VariableRenderer(make_source_resolver({"v": 1}))
        result = await renderer.render("${v as boolean}")
        assert result is True

    @pytest.mark.anyio
    async def test_int_zero(self):
        """Test that integer 0 converts to False."""
        renderer = VariableRenderer(make_source_resolver({"v": 0}))
        result = await renderer.render("${v as boolean}")
        assert result is False


# ============================
# json conversion
# ============================

class TestConvertJson:
    """Test 'as json' type conversion."""

    @pytest.mark.anyio
    async def test_json_string_to_dict(self):
        """Test that a JSON object string is parsed to dict."""
        renderer = VariableRenderer(make_source_resolver({"v": '{"key": "value"}'}))
        result = await renderer.render("${v as json}")
        assert result == {"key": "value"}

    @pytest.mark.anyio
    async def test_json_string_to_list(self):
        """Test that a JSON array string is parsed to list."""
        renderer = VariableRenderer(make_source_resolver({"v": "[1, 2, 3]"}))
        result = await renderer.render("${v as json}")
        assert result == [1, 2, 3]

    @pytest.mark.anyio
    async def test_dict_passthrough(self):
        """Test that a dict value passes through unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": {"already": "parsed"}}))
        result = await renderer.render("${v as json}")
        assert result == {"already": "parsed"}

    @pytest.mark.anyio
    async def test_list_passthrough(self):
        """Test that a list value passes through unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": [1, 2]}))
        result = await renderer.render("${v as json}")
        assert result == [1, 2]

    @pytest.mark.anyio
    async def test_int_passthrough(self):
        """Test that an int value passes through unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": 42}))
        result = await renderer.render("${v as json}")
        assert result == 42

    @pytest.mark.anyio
    async def test_json_string_number(self):
        """Test that a numeric string is parsed to int."""
        renderer = VariableRenderer(make_source_resolver({"v": "42"}))
        result = await renderer.render("${v as json}")
        assert result == 42


# ============================
# object[] conversion
# ============================

class TestConvertObjectArray:
    """Test 'as object[]' type conversion with field projection."""

    @pytest.mark.anyio
    async def test_filter_dicts_from_list(self):
        """Test that only dict items are kept from a mixed list."""
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"a": 1}, "skip", {"b": 2}, 42]
        }))
        result = await renderer.render("${v as object[]}")
        assert result == [{"a": 1}, {"b": 2}]

    @pytest.mark.anyio
    async def test_with_subtype_field_projection(self):
        """Test single field projection on object array."""
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        }))
        result = await renderer.render("${v as object[]/name}")
        assert result == [{"name": "Alice"}, {"name": "Bob"}]

    @pytest.mark.anyio
    async def test_with_multiple_subtype_fields(self):
        """Test multiple field projection on object array."""
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"name": "Alice", "age": 30, "city": "Seoul"}]
        }))
        result = await renderer.render("${v as object[]/name,age}")
        assert result == [{"name": "Alice", "age": 30}]

    @pytest.mark.anyio
    async def test_non_list_returns_empty(self):
        """Test that a non-list value returns empty list."""
        renderer = VariableRenderer(make_source_resolver({"v": "not a list"}))
        result = await renderer.render("${v as object[]}")
        assert result == []

    @pytest.mark.anyio
    async def test_empty_list(self):
        """Test that an empty list returns empty list."""
        renderer = VariableRenderer(make_source_resolver({"v": []}))
        result = await renderer.render("${v as object[]}")
        assert result == []

    @pytest.mark.anyio
    async def test_nested_path_in_subtype(self):
        """Test nested dot-path field projection."""
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"data": {"value": 1}}, {"data": {"value": 2}}]
        }))
        result = await renderer.render("${v as object[]/data.value}")
        assert result == [{"value": 1}, {"value": 2}]


# ============================
# base64 conversion
# ============================

class TestConvertBase64:
    """Test 'as base64' type conversion."""

    @pytest.mark.anyio
    async def test_bytes_to_base64(self):
        """Test that bytes are encoded to base64 string."""
        renderer = VariableRenderer(make_source_resolver({"v": b"hello"}))
        result = await renderer.render("${v as base64}")
        assert base64.b64decode(result) == b"hello"

    @pytest.mark.anyio
    async def test_upload_file_to_base64(self):
        """Test that UploadFile content is encoded to base64."""
        file = UploadFile(file=io.BytesIO(b"file content"), filename="test.txt")
        renderer = VariableRenderer(make_source_resolver({"v": file}))
        result = await renderer.render("${v as base64}")
        assert base64.b64decode(result) == b"file content"

    @pytest.mark.anyio
    async def test_stream_resource_to_base64(self):
        """Test that StreamResource content is encoded to base64."""
        resource = BytesStreamResource(b"stream data")
        renderer = VariableRenderer(make_source_resolver({"v": resource}))
        result = await renderer.render("${v as base64}")
        assert base64.b64decode(result) == b"stream data"


# ============================
# file type conversion (image, audio, video, file)
# ============================

class TestConvertFileTypes:
    """Test file type conversions (image, audio, video, file)."""

    @pytest.mark.anyio
    async def test_upload_file_with_path_format(self):
        """Test that UploadFile with format=path saves to temporary file and returns path."""
        file = UploadFile(file=io.BytesIO(b"img data"), filename="test.png")
        renderer = VariableRenderer(make_source_resolver({"v": file}))
        result = await renderer.render("${v as image;path}")
        assert isinstance(result, str)
        assert result.endswith(".png")

    @pytest.mark.anyio
    async def test_ignore_files_returns_value_as_is(self):
        """Test that with ignore_files=True, non-UploadFile values pass through."""
        renderer = VariableRenderer(make_source_resolver({"v": "/path/to/file.png"}))
        result = await renderer.render("${v as image}")
        assert result == "/path/to/file.png"

    @pytest.mark.anyio
    async def test_upload_file_without_path_format_returns_as_is(self):
        """Test that UploadFile without path format passes through when ignore_files=True."""
        file = UploadFile(file=io.BytesIO(b"data"), filename="test.wav")
        renderer = VariableRenderer(make_source_resolver({"v": file}))
        result = await renderer.render("${v as audio}")
        assert isinstance(result, UploadFile)

    @pytest.mark.anyio
    async def test_ignore_files_false_creates_upload_file(self):
        """Test that with ignore_files=False, bytes are saved and wrapped in UploadFile."""
        resource = BytesStreamResource(b"audio data")
        renderer = VariableRenderer(make_source_resolver({"v": resource}))
        result = await renderer.render("${v as audio/wav}", ignore_files=False)
        assert isinstance(result, UploadFile)

    @pytest.mark.anyio
    async def test_file_type_video(self):
        """Test that video type behaves the same as image/audio."""
        renderer = VariableRenderer(make_source_resolver({"v": "video.mp4"}))
        result = await renderer.render("${v as video}")
        assert result == "video.mp4"

    @pytest.mark.anyio
    async def test_file_type_file(self):
        """Test that generic file type behaves the same."""
        renderer = VariableRenderer(make_source_resolver({"v": "doc.pdf"}))
        result = await renderer.render("${v as file}")
        assert result == "doc.pdf"


# ============================
# unknown type fallback
# ============================

class TestConvertUnknownType:
    """Test that unknown type names return values unchanged."""

    @pytest.mark.anyio
    async def test_unknown_type_returns_value_as_is(self):
        """Test that a string value passes through for unknown type."""
        renderer = VariableRenderer(make_source_resolver({"v": "hello"}))
        result = await renderer.render("${v as unknown_type}")
        assert result == "hello"

    @pytest.mark.anyio
    async def test_unknown_type_with_dict(self):
        """Test that a dict value passes through for unknown type."""
        renderer = VariableRenderer(make_source_resolver({"v": {"key": "value"}}))
        result = await renderer.render("${v as custom}")
        assert result == {"key": "value"}

    @pytest.mark.anyio
    async def test_unknown_type_returns_async_iterator_as_is(self):
        """Test that an AsyncIterator passes through for unknown type."""
        renderer = VariableRenderer(make_source_resolver({"v": make_async_iterator([b"a", b"b"])}))
        result = await renderer.render("${v as custom}")
        assert isinstance(result, AsyncIterator)
        chunks = await collect_async(result)
        assert chunks == [b"a", b"b"]


# ============================
# AsyncIterator pass-through (audio/video/image/file)
# ============================

class TestAsyncIteratorPassThrough:
    """Test that AsyncIterator values pass through for file-like types."""

    @pytest.mark.anyio
    async def test_audio_type_returns_async_iterator_as_is(self):
        """Test that audio type returns AsyncIterator unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": make_async_iterator([b"pcm"])}))
        result = await renderer.render("${v as audio/pcm}")
        assert isinstance(result, AsyncIterator)
        chunks = await collect_async(result)
        assert chunks == [b"pcm"]

    @pytest.mark.anyio
    async def test_video_type_returns_async_iterator_as_is(self):
        """Test that video type returns AsyncIterator unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": make_async_iterator([b"frame"])}))
        result = await renderer.render("${v as video/mp4}")
        assert isinstance(result, AsyncIterator)
        chunks = await collect_async(result)
        assert chunks == [b"frame"]

    @pytest.mark.anyio
    async def test_image_type_returns_async_iterator_as_is(self):
        """Test that image type returns AsyncIterator unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": make_async_iterator([b"px"])}))
        result = await renderer.render("${v as image/png}")
        assert isinstance(result, AsyncIterator)
        chunks = await collect_async(result)
        assert chunks == [b"px"]

    @pytest.mark.anyio
    async def test_file_type_returns_async_iterator_as_is(self):
        """Test that file type returns AsyncIterator unchanged."""
        renderer = VariableRenderer(make_source_resolver({"v": make_async_iterator([b"data"])}))
        result = await renderer.render("${v as file}")
        assert isinstance(result, AsyncIterator)
        chunks = await collect_async(result)
        assert chunks == [b"data"]

    @pytest.mark.anyio
    async def test_audio_iterator_preserves_chunks(self):
        """Test that all chunks from an audio AsyncIterator are preserved."""
        renderer = VariableRenderer(make_source_resolver({"v": make_async_iterator([b"a", b"b", b"c"])}))
        result = await renderer.render("${v as audio/pcm}")
        chunks = await collect_async(result)
        assert chunks == [b"a", b"b", b"c"]


# ============================
# sse-text conversion
# ============================

class TestSseTextFromAsyncIterator:
    """Test sse-text conversion from AsyncIterator input."""

    @pytest.mark.anyio
    async def test_async_iterator_wrapped_in_iterator_stream_resource(self):
        """Test that AsyncIterator input produces EventIteratorStreamResource."""
        aiter = make_async_iterator(["chunk1", "chunk2"])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as sse-text}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.content_type == "text/event-stream"
        assert result.format == StreamFormat.TEXT

    @pytest.mark.anyio
    async def test_async_iterator_chunks_preserved(self):
        """Test that chunks from the original iterator are passed through."""
        aiter = make_async_iterator(["hello", "world"])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as sse-text}")
        chunks = await collect_async(result)

        assert chunks == ["hello", "world"]


class TestSseTextFromStreamResource:
    """Test sse-text conversion from StreamResource input."""

    @pytest.mark.anyio
    async def test_stream_resource_wrapped_in_iterator_stream_resource(self):
        """Test that StreamResource input is wrapped in EventIteratorStreamResource."""
        resource = BytesStreamResource(b"hello", "application/octet-stream")
        renderer = VariableRenderer(make_source_resolver({"output": resource}))

        result = await renderer.render("${output as sse-text}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.content_type == "text/event-stream"
        assert result.format == StreamFormat.TEXT

    @pytest.mark.anyio
    async def test_stream_resource_bytes_iterable(self):
        """Test that bytes from StreamResource are yielded through EventIteratorStreamResource."""
        resource = BytesStreamResource(b"data", "application/octet-stream")
        renderer = VariableRenderer(make_source_resolver({"output": resource}))

        result = await renderer.render("${output as sse-text}")
        chunks = await collect_async(result)

        assert len(chunks) > 0
        assert b"data" in b"".join(chunks)


class TestSseTextFromPlainValue:
    """Test sse-text conversion from plain scalar values."""

    @pytest.mark.anyio
    async def test_string_value_wrapped_as_single_event(self):
        """Test that a plain string is wrapped as single-yield EventIteratorStreamResource."""
        renderer = VariableRenderer(make_source_resolver({"output": "hello"}))

        result = await renderer.render("${output as sse-text}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.content_type == "text/event-stream"
        assert result.format == StreamFormat.TEXT

        chunks = await collect_async(result)
        assert chunks == ["hello"]

    @pytest.mark.anyio
    async def test_dict_value_wrapped_as_single_event(self):
        """Test that a dict is wrapped as single-yield EventIteratorStreamResource."""
        renderer = VariableRenderer(make_source_resolver({"output": {"key": "value"}}))

        result = await renderer.render("${output as sse-text}")

        assert isinstance(result, EventIteratorStreamResource)
        chunks = await collect_async(result)
        assert chunks == [{"key": "value"}]

    @pytest.mark.anyio
    async def test_int_value_wrapped_as_single_event(self):
        """Test that an integer is wrapped as single-yield EventIteratorStreamResource."""
        renderer = VariableRenderer(make_source_resolver({"output": 42}))

        result = await renderer.render("${output as sse-text}")

        chunks = await collect_async(result)
        assert chunks == [42]

    @pytest.mark.anyio
    async def test_list_value_wrapped_as_single_event(self):
        """Test that a list is wrapped as single-yield EventIteratorStreamResource."""
        renderer = VariableRenderer(make_source_resolver({"output": [1, 2, 3]}))

        result = await renderer.render("${output as sse-text}")

        chunks = await collect_async(result)
        assert chunks == [[1, 2, 3]]


# ============================
# sse-json conversion
# ============================

class TestSseJsonFromAsyncIterator:
    """Test sse-json conversion from AsyncIterator input."""

    @pytest.mark.anyio
    async def test_async_iterator_has_json_format(self):
        """Test that AsyncIterator with sse-json gets StreamFormat.JSON."""
        aiter = make_async_iterator([{"a": 1}])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as sse-json}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.format == StreamFormat.JSON

    @pytest.mark.anyio
    async def test_async_iterator_chunks_preserved(self):
        """Test that chunks are passed through with JSON format set."""
        aiter = make_async_iterator([{"a": 1}, {"b": 2}])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as sse-json}")
        chunks = await collect_async(result)

        assert chunks == [{"a": 1}, {"b": 2}]


class TestSseJsonFromStreamResource:
    """Test sse-json conversion from StreamResource input."""

    @pytest.mark.anyio
    async def test_stream_resource_has_json_format(self):
        """Test that StreamResource with sse-json gets StreamFormat.JSON."""
        resource = BytesStreamResource(b"data", "application/octet-stream")
        renderer = VariableRenderer(make_source_resolver({"output": resource}))

        result = await renderer.render("${output as sse-json}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.format == StreamFormat.JSON


class TestSseJsonFromPlainValue:
    """Test sse-json conversion from plain scalar values."""

    @pytest.mark.anyio
    async def test_dict_wrapped_with_json_format(self):
        """Test that a dict value is wrapped as single event with JSON format."""
        renderer = VariableRenderer(make_source_resolver({"output": {"key": "value"}}))

        result = await renderer.render("${output as sse-json}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.format == StreamFormat.JSON
        chunks = await collect_async(result)
        assert chunks == [{"key": "value"}]

    @pytest.mark.anyio
    async def test_string_wrapped_with_json_format(self):
        """Test that a string value is wrapped as single event with JSON format."""
        renderer = VariableRenderer(make_source_resolver({"output": "hello"}))

        result = await renderer.render("${output as sse-json}")

        chunks = await collect_async(result)
        assert chunks == ["hello"]


# ============================
# Edge cases
# ============================

class TestSseEdgeCases:
    """Test SSE conversion edge cases."""

    @pytest.mark.anyio
    async def test_none_value_not_converted(self):
        """Test that None value is not converted (type conversion requires non-None)."""
        renderer = VariableRenderer(make_source_resolver({"output": None}))

        result = await renderer.render("${output as sse-text}")

        # When value is None, _convert_value_to_type is not called
        assert result is None

    @pytest.mark.anyio
    async def test_sse_text_in_full_expression(self):
        """Test that SSE type works with full variable expression syntax."""
        aiter = make_async_iterator(["data"])
        renderer = VariableRenderer(make_source_resolver({"result": [aiter]}))

        result = await renderer.render("${result[0] as sse-text}")

        assert isinstance(result, EventIteratorStreamResource)
        assert result.format == StreamFormat.TEXT

    @pytest.mark.anyio
    async def test_sse_type_returns_raw_object_not_string(self):
        """Test that sse-text returns the raw object, not a stringified version."""
        renderer = VariableRenderer(make_source_resolver({"output": "hello"}))

        result = await renderer.render("${output as sse-text}")

        # Should be EventIteratorStreamResource, not a string
        assert isinstance(result, EventIteratorStreamResource)

    @pytest.mark.anyio
    async def test_stream_resource_isinstance_before_async_iterator(self):
        """Test that StreamResource is matched before AsyncIterator check."""
        resource = BytesStreamResource(b"test", "application/octet-stream")

        # StreamResource implements __aiter__, so isinstance(resource, AsyncIterator) may be True
        # But the code checks StreamResource first
        renderer = VariableRenderer(make_source_resolver({"output": resource}))
        result = await renderer.render("${output as sse-text}")

        assert isinstance(result, EventIteratorStreamResource)
        # The inner iterator should be the original resource, not doubly-wrapped
        assert result.iterator is resource


# ============================
# List spread
# ============================

class TestSpreadList:
    """Test list spread operations with '...${var}' syntax."""

    @pytest.mark.anyio
    async def test_basic_spread(self):
        """Test that spread inserts list items inline."""
        renderer = VariableRenderer(make_source_resolver({
            "items": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        }))
        result = await renderer.render([
            {"role": "system", "content": "prompt"},
            "...${items}",
            {"role": "user", "content": "bye"},
        ])
        assert result == [
            {"role": "system", "content": "prompt"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "bye"},
        ]

    @pytest.mark.anyio
    async def test_spread_empty_list(self):
        """Test that spreading an empty list adds nothing."""
        renderer = VariableRenderer(make_source_resolver({"items": []}))
        result = await renderer.render(["before", "...${items}", "after"])
        assert result == ["before", "after"]

    @pytest.mark.anyio
    async def test_spread_none_skips(self):
        """Test that spreading None skips the entry."""
        renderer = VariableRenderer(make_source_resolver({"items": None}))
        result = await renderer.render(["before", "...${items}", "after"])
        assert result == ["before", "after"]

    @pytest.mark.anyio
    async def test_multiple_spreads(self):
        """Test multiple spread expressions in one list."""
        renderer = VariableRenderer(make_source_resolver({
            "a": [1, 2],
            "b": [3, 4],
        }))
        result = await renderer.render(["...${a}", "middle", "...${b}"])
        assert result == [1, 2, "middle", 3, 4]

    @pytest.mark.anyio
    async def test_spread_non_list_raises(self):
        """Test that spreading a non-list value raises ValueError."""
        renderer = VariableRenderer(make_source_resolver({"items": "not a list"}))
        with pytest.raises(ValueError, match="Spread in list must resolve to a list"):
            await renderer.render(["...${items}"])

    @pytest.mark.anyio
    async def test_spread_with_path(self):
        """Test spread with a nested dot-path variable."""
        renderer = VariableRenderer(make_source_resolver({
            "jobs": {"load": {"output": {"messages": [{"role": "user", "content": "test"}]}}}
        }))
        result = await renderer.render(["...${jobs.load.output.messages}"])
        assert result == [{"role": "user", "content": "test"}]

    @pytest.mark.anyio
    async def test_non_spread_with_dots_prefix(self):
        """Test that text starting with ... but not a valid spread is treated as normal string."""
        renderer = VariableRenderer(make_source_resolver({"items": [1, 2]}))
        result = await renderer.render(["...${items} extra"])
        assert result == ["...[1, 2] extra"]

    @pytest.mark.anyio
    async def test_non_spread_dots_without_var(self):
        """Test that plain '...' without ${} is treated as normal string."""
        renderer = VariableRenderer(make_source_resolver({}))
        result = await renderer.render(["...", "normal"])
        assert result == ["...", "normal"]


# ============================
# Dict spread
# ============================

class TestSpreadDict:
    """Test dict spread operations with '...' key syntax."""

    @pytest.mark.anyio
    async def test_basic_spread(self):
        """Test that spread merges dict entries inline."""
        renderer = VariableRenderer(make_source_resolver({
            "extra": {"Authorization": "Bearer token", "X-Custom": "value"}
        }))
        result = await renderer.render({
            "Content-Type": "application/json",
            "...": "${extra}",
        })
        assert result == {
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
            "X-Custom": "value",
        }

    @pytest.mark.anyio
    async def test_spread_empty_dict(self):
        """Test that spreading an empty dict adds nothing."""
        renderer = VariableRenderer(make_source_resolver({"extra": {}}))
        result = await renderer.render({"key": "value", "...": "${extra}"})
        assert result == {"key": "value"}

    @pytest.mark.anyio
    async def test_spread_none_skips(self):
        """Test that spreading None skips the entry."""
        renderer = VariableRenderer(make_source_resolver({"extra": None}))
        result = await renderer.render({"key": "value", "...": "${extra}"})
        assert result == {"key": "value"}

    @pytest.mark.anyio
    async def test_spread_overwrites_earlier_keys(self):
        """Test that spread values overwrite earlier keys."""
        renderer = VariableRenderer(make_source_resolver({
            "extra": {"key": "overwritten"}
        }))
        result = await renderer.render({"key": "original", "...": "${extra}"})
        assert result == {"key": "overwritten"}

    @pytest.mark.anyio
    async def test_spread_non_dict_raises(self):
        """Test that spreading a non-dict value raises ValueError."""
        renderer = VariableRenderer(make_source_resolver({"extra": [1, 2]}))
        with pytest.raises(ValueError, match="Spread in dict must resolve to a dict"):
            await renderer.render({"...": "${extra}"})

    @pytest.mark.anyio
    async def test_spread_with_path(self):
        """Test spread with a nested dot-path variable."""
        renderer = VariableRenderer(make_source_resolver({
            "jobs": {"auth": {"output": {"headers": {"Token": "abc"}}}}
        }))
        result = await renderer.render({
            "Host": "example.com",
            "...": "${jobs.auth.output.headers}",
        })
        assert result == {"Host": "example.com", "Token": "abc"}
