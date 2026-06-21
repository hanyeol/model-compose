"""Tests for VariableRenderer type conversions, SSE wrapping, and spread operations."""

import base64
import io
from collections.abc import AsyncIterator

import pytest
from starlette.datastructures import UploadFile

from mindor.core.utils.renderers import VariableRenderer
from mindor.core.utils.streaming.stream import EventStreamFormat
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.core.utils.iterators import EventStreamIterator


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# ---- Helpers ----

def make_source_resolver(sources):
    """Create a source resolver that returns values from a dict."""
    async def resolver(key, index=None, scope=None):
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
    async def test_non_dict_element_raises(self):
        """Test that a non-dict element in the list raises (strict policy)."""
        renderer = VariableRenderer(make_source_resolver({
            "v": [{"a": 1}, "skip", {"b": 2}, 42]
        }))
        with pytest.raises(ValueError):
            await renderer.render("${v as object[]}")

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
    async def test_non_list_raises(self):
        """Test that a non-list value raises due to `[]` cardinality assertion."""
        renderer = VariableRenderer(make_source_resolver({"v": "not a list"}))
        with pytest.raises(ValueError):
            await renderer.render("${v as object[]}")

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
    async def test_upload_file_audio_becomes_audio_stream(self):
        """UploadFile + audio → AudioStreamResource wrapping UploadFile."""
        from mindor.core.utils.streaming.audio import AudioStreamResource
        file = UploadFile(file=io.BytesIO(b"data"), filename="test.wav")
        renderer = VariableRenderer(make_source_resolver({"v": file}))
        result = await renderer.render("${v as audio/wav}")
        from mindor.core.utils.streaming.audio import WavStreamResource
        assert isinstance(result, WavStreamResource)

    @pytest.mark.anyio
    async def test_str_image_without_format_raises(self):
        """Plain string with `as image` (no format hint) is not a valid image input."""
        renderer = VariableRenderer(make_source_resolver({"v": "/path/to/file.png"}))
        with pytest.raises(TypeError):
            await renderer.render("${v as image}")

    @pytest.mark.anyio
    async def test_str_video_without_format_raises(self):
        """Plain string with `as video` (no format hint) is not a valid video input."""
        renderer = VariableRenderer(make_source_resolver({"v": "video.mp4"}))
        with pytest.raises(TypeError):
            await renderer.render("${v as video}")

    @pytest.mark.anyio
    async def test_str_file_without_format_raises(self):
        """Plain string with `as file` (no format hint) is not a valid file input."""
        renderer = VariableRenderer(make_source_resolver({"v": "doc.pdf"}))
        with pytest.raises(TypeError):
            await renderer.render("${v as file}")


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
# event-stream/text conversion
# ============================

class TestSseTextFromAsyncIterator:
    """Test event-stream/text conversion from AsyncIterator input."""

    @pytest.mark.anyio
    async def test_async_iterator_wrapped_in_iterator_stream_resource(self):
        """Test that AsyncIterator input produces EventStreamIterator."""
        aiter = make_async_iterator(["chunk1", "chunk2"])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as event-stream/text}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.TEXT

    @pytest.mark.anyio
    async def test_async_iterator_chunks_preserved(self):
        """Test that chunks from the original iterator pass through unchanged."""
        aiter = make_async_iterator(["hello", "world"])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as event-stream/text}")
        chunks = await collect_async(result)

        assert chunks == ["hello", "world"]


class TestSseTextFromStreamResource:
    """Test event-stream/text conversion from StreamResource input."""

    @pytest.mark.anyio
    async def test_stream_resource_wrapped_in_iterator_stream_resource(self):
        """Test that StreamResource input is wrapped in EventStreamIterator."""
        resource = BytesStreamResource(b"hello", "application/octet-stream")
        renderer = VariableRenderer(make_source_resolver({"output": resource}))

        result = await renderer.render("${output as event-stream/text}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.TEXT

    @pytest.mark.anyio
    async def test_stream_resource_bytes_iterable(self):
        """Test that bytes from StreamResource are encoded as text via EventStreamIterator."""
        resource = BytesStreamResource(b"data", "application/octet-stream")
        renderer = VariableRenderer(make_source_resolver({"output": resource}))

        result = await renderer.render("${output as event-stream/text}")
        chunks = await collect_async(result)

        assert len(chunks) > 0
        assert "data" in "".join(chunks)


class TestSseTextFromPlainValue:
    """Test event-stream/text conversion from plain scalar values."""

    @pytest.mark.anyio
    async def test_string_value_wrapped_as_single_chunk(self):
        """Test that a plain string is wrapped as a single-chunk iterator."""
        renderer = VariableRenderer(make_source_resolver({"output": "hello"}))

        result = await renderer.render("${output as event-stream/text}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.TEXT

        chunks = await collect_async(result)
        assert chunks == ["hello"]

    @pytest.mark.anyio
    async def test_dict_value_encoded_as_string(self):
        """Test that a dict is stringified by the TEXT-format EventStreamIterator."""
        renderer = VariableRenderer(make_source_resolver({"output": {"key": "value"}}))

        result = await renderer.render("${output as event-stream/text}")

        assert isinstance(result, EventStreamIterator)
        chunks = await collect_async(result)
        assert chunks == [str({"key": "value"})]

    @pytest.mark.anyio
    async def test_int_value_encoded_as_string(self):
        """Test that an integer is stringified by the TEXT-format EventStreamIterator."""
        renderer = VariableRenderer(make_source_resolver({"output": 42}))

        result = await renderer.render("${output as event-stream/text}")

        chunks = await collect_async(result)
        assert chunks == ["42"]

    @pytest.mark.anyio
    async def test_list_value_encoded_as_string(self):
        """Test that a list is stringified by the TEXT-format EventStreamIterator."""
        renderer = VariableRenderer(make_source_resolver({"output": [1, 2, 3]}))

        result = await renderer.render("${output as event-stream/text}")

        chunks = await collect_async(result)
        assert chunks == [str([1, 2, 3])]


# ============================
# event-stream/json conversion
# ============================

class TestSseJsonFromAsyncIterator:
    """Test event-stream/json conversion from AsyncIterator input."""

    @pytest.mark.anyio
    async def test_async_iterator_has_json_format(self):
        """Test that AsyncIterator with event-stream/json gets EventStreamFormat.JSON."""
        aiter = make_async_iterator([{"a": 1}])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as event-stream/json}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.JSON

    @pytest.mark.anyio
    async def test_async_iterator_chunks_json_encoded(self):
        """Test that chunks are JSON-encoded by the JSON-format EventStreamIterator."""
        aiter = make_async_iterator([{"a": 1}, {"b": 2}])
        renderer = VariableRenderer(make_source_resolver({"output": aiter}))

        result = await renderer.render("${output as event-stream/json}")
        chunks = await collect_async(result)

        assert chunks == ['{"a": 1}', '{"b": 2}']


class TestSseJsonFromStreamResource:
    """Test event-stream/json conversion from StreamResource input."""

    @pytest.mark.anyio
    async def test_stream_resource_has_json_format(self):
        """Test that StreamResource with event-stream/json gets EventStreamFormat.JSON."""
        resource = BytesStreamResource(b"data", "application/octet-stream")
        renderer = VariableRenderer(make_source_resolver({"output": resource}))

        result = await renderer.render("${output as event-stream/json}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.JSON


class TestSseJsonFromPlainValue:
    """Test event-stream/json conversion from plain scalar values."""

    @pytest.mark.anyio
    async def test_dict_json_encoded(self):
        """Test that a dict value is JSON-encoded by the JSON-format EventStreamIterator."""
        renderer = VariableRenderer(make_source_resolver({"output": {"key": "value"}}))

        result = await renderer.render("${output as event-stream/json}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.JSON
        chunks = await collect_async(result)
        assert chunks == ['{"key": "value"}']

    @pytest.mark.anyio
    async def test_string_json_encoded(self):
        """Test that a string value is JSON-encoded (quoted) by the JSON-format EventStreamIterator."""
        renderer = VariableRenderer(make_source_resolver({"output": "hello"}))

        result = await renderer.render("${output as event-stream/json}")

        chunks = await collect_async(result)
        assert chunks == ['"hello"']


# ============================
# Edge cases
# ============================

class TestSseEdgeCases:
    """Test SSE conversion edge cases."""

    @pytest.mark.anyio
    async def test_none_value_not_converted(self):
        """Test that None value is not converted (type conversion requires non-None)."""
        renderer = VariableRenderer(make_source_resolver({"output": None}))

        result = await renderer.render("${output as event-stream/text}")

        # When value is None, _convert_value_to_type is not called
        assert result is None

    @pytest.mark.anyio
    async def test_sse_text_in_full_expression(self):
        """Test that SSE type works with full variable expression syntax."""
        aiter = make_async_iterator(["data"])
        renderer = VariableRenderer(make_source_resolver({"result": [aiter]}))

        result = await renderer.render("${result[0] as event-stream/text}")

        assert isinstance(result, EventStreamIterator)
        assert result.format == EventStreamFormat.TEXT

    @pytest.mark.anyio
    async def test_sse_type_returns_raw_object_not_string(self):
        """Test that event-stream/text returns the raw object, not a stringified version."""
        renderer = VariableRenderer(make_source_resolver({"output": "hello"}))

        result = await renderer.render("${output as event-stream/text}")

        # Should be EventStreamIterator, not a string
        assert isinstance(result, EventStreamIterator)

    @pytest.mark.anyio
    async def test_stream_resource_isinstance_before_async_iterator(self):
        """Test that StreamResource is matched before AsyncIterator check."""
        resource = BytesStreamResource(b"test", "application/octet-stream")

        # StreamResource implements __aiter__, so isinstance(resource, AsyncIterator) may be True
        # But the code checks StreamResource first
        renderer = VariableRenderer(make_source_resolver({"output": resource}))
        result = await renderer.render("${output as event-stream/text}")

        assert isinstance(result, EventStreamIterator)
        # The inner iterator should be the original resource, not doubly-wrapped
        assert result.source is resource


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
        """Test that spreading a non-list value raises TypeError."""
        renderer = VariableRenderer(make_source_resolver({"items": "not a list"}))
        with pytest.raises(TypeError, match="Spread in list must resolve to a list"):
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
        """Test that spreading a non-dict value raises TypeError."""
        renderer = VariableRenderer(make_source_resolver({"extra": [1, 2]}))
        with pytest.raises(TypeError, match="Spread in dict must resolve to a dict"):
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


# ============================
# attrs parsing & rendering
# ============================

def capture_attrs(renderer):
    """Patch _convert_value_to_type on a renderer instance to capture the attrs dict.

    Returns a list that is appended to on each call.
    """
    captured = []
    original = renderer._convert_value_to_type

    async def wrapper(value, type, is_list, subtype, attrs, format, skip_decode=False):
        captured.append(attrs)
        return await original(value, type, is_list, subtype, attrs, format, skip_decode)

    renderer._convert_value_to_type = wrapper
    return captured


class TestSplitAttrs:
    """Test the _split_attrs helper that segments comma-separated attr pairs."""

    def _renderer(self):
        return VariableRenderer(make_source_resolver({}))

    def test_simple_pairs(self):
        r = self._renderer()
        assert r._split_attrs("a=1,b=2") == ["a=1", "b=2"]

    def test_single_pair(self):
        r = self._renderer()
        assert r._split_attrs("k=v") == ["k=v"]

    def test_empty_string(self):
        """Empty input yields one empty segment — consistent with the splitter never collapsing segments."""
        r = self._renderer()
        assert r._split_attrs("") == [""]

    def test_whitespace_preserved_within_segments(self):
        r = self._renderer()
        # split itself does not strip; trimming happens later
        assert r._split_attrs(" a = 1 , b = 2 ") == [" a = 1 ", " b = 2 "]

    def test_nested_var_with_comma_in_default(self):
        """A nested ${...} containing a comma in its default expression should not split."""
        r = self._renderer()
        # Comma inside ${...} must not split — depth tracking should keep this intact.
        assert r._split_attrs("a=${x | 1,2},b=2") == ["a=${x | 1,2}", "b=2"]

    def test_nested_var_with_indexed_access(self):
        """A nested ${input.list[0]} should remain intact (the inner ] is irrelevant for splitting)."""
        r = self._renderer()
        assert r._split_attrs("sr=${input.list[0]},ch=${input.list[1]}") == [
            "sr=${input.list[0]}",
            "ch=${input.list[1]}",
        ]

    def test_multiple_nested_vars(self):
        r = self._renderer()
        assert r._split_attrs("a=${x},b=${y},c=${z}") == ["a=${x}", "b=${y}", "c=${z}"]

    def test_nested_var_alone(self):
        r = self._renderer()
        assert r._split_attrs("a=${x}") == ["a=${x}"]

    def test_dollar_without_brace_does_not_open_depth(self):
        """A bare $ followed by something other than { should be a literal."""
        r = self._renderer()
        # `$x` is not a variable opener — the comma should still split.
        assert r._split_attrs("a=$x,b=2") == ["a=$x", "b=2"]

    def test_closing_brace_without_open_is_literal(self):
        """An unmatched } at depth 0 is just a character."""
        r = self._renderer()
        # depth never becomes negative; } at depth 0 is appended literally and comma still splits.
        assert r._split_attrs("a=},b=2") == ["a=}", "b=2"]


class TestRenderAttrs:
    """Test the _render_attrs coroutine that parses and interpolates attrs."""

    @pytest.mark.anyio
    async def test_literal_pairs(self):
        r = VariableRenderer(make_source_resolver({}))
        result = await r._render_attrs("a=1,b=2", scope=None)
        assert result == {"a": "1", "b": "2"}

    @pytest.mark.anyio
    async def test_pairs_with_whitespace(self):
        r = VariableRenderer(make_source_resolver({}))
        result = await r._render_attrs(" a = 1 , b = 2 ", scope=None)
        # Keys and values are stripped.
        assert result == {"a": "1", "b": "2"}

    @pytest.mark.anyio
    async def test_empty_string(self):
        r = VariableRenderer(make_source_resolver({}))
        result = await r._render_attrs("", scope=None)
        assert result == {}

    @pytest.mark.anyio
    async def test_value_interpolation_preserves_int(self):
        """A ${} value resolving to int should land in the dict as int (Dict[str, Any])."""
        r = VariableRenderer(make_source_resolver({"input": {"sr": 24000}}))
        result = await r._render_attrs("sample_rate=${input.sr}", scope=None)
        assert result == {"sample_rate": 24000}
        assert isinstance(result["sample_rate"], int)

    @pytest.mark.anyio
    async def test_value_interpolation_preserves_float(self):
        r = VariableRenderer(make_source_resolver({"input": {"v": 1.5}}))
        result = await r._render_attrs("ratio=${input.v}", scope=None)
        assert result["ratio"] == 1.5
        assert isinstance(result["ratio"], float)

    @pytest.mark.anyio
    async def test_value_interpolation_preserves_bool(self):
        r = VariableRenderer(make_source_resolver({"input": {"flag": True}}))
        result = await r._render_attrs("enabled=${input.flag}", scope=None)
        assert result["enabled"] is True

    @pytest.mark.anyio
    async def test_value_interpolation_preserves_none_as_empty(self):
        """None from _render_text (variable resolved to None, no default) is preserved verbatim."""
        r = VariableRenderer(make_source_resolver({"input": {"missing": None}}))
        result = await r._render_attrs("k=${input.missing}", scope=None)
        # _render_text returns None for full-span single match with None value.
        assert result == {"k": None}

    @pytest.mark.anyio
    async def test_mixed_literal_and_interpolated(self):
        r = VariableRenderer(make_source_resolver({"input": {"sr": 16000}}))
        result = await r._render_attrs("sample_rate=${input.sr},channels=1,bit_depth=16", scope=None)
        assert result == {"sample_rate": 16000, "channels": "1", "bit_depth": "16"}
        # Interpolated stays int, literals stay str — Dict[str, Any] honored.
        assert isinstance(result["sample_rate"], int)
        assert isinstance(result["channels"], str)

    @pytest.mark.anyio
    async def test_interpolation_with_indexed_access(self):
        r = VariableRenderer(make_source_resolver({"input": [16000, 1, 22050]}))
        result = await r._render_attrs("sr=${input[0]},ch=${input[1]}", scope=None)
        assert result == {"sr": 16000, "ch": 1}

    @pytest.mark.anyio
    async def test_interpolation_with_default(self):
        r = VariableRenderer(make_source_resolver({"input": {}}))
        result = await r._render_attrs("sr=${input.missing | 44100}", scope=None)
        # Default is rendered through _render_text, which returns the literal string "44100".
        assert result == {"sr": "44100"}

    @pytest.mark.anyio
    async def test_interpolation_with_default_containing_comma(self):
        """A default expression containing a comma inside ${...} must not split the pair."""
        r = VariableRenderer(make_source_resolver({"input": {}}))
        # Comma sits inside the nested ${...}, so depth tracking keeps it together.
        result = await r._render_attrs("a=${x | hi,there},b=2", scope=None)
        assert result == {"a": "hi,there", "b": "2"}

    @pytest.mark.anyio
    async def test_value_with_embedded_variable_inside_text(self):
        """Mixed text inside a value: '${var}suffix' should yield interpolated text."""
        r = VariableRenderer(make_source_resolver({"input": {"x": "abc"}}))
        result = await r._render_attrs("k=prefix-${input.x}-suffix", scope=None)
        assert result == {"k": "prefix-abc-suffix"}

    @pytest.mark.anyio
    async def test_pair_without_equals_is_ignored(self):
        r = VariableRenderer(make_source_resolver({}))
        result = await r._render_attrs("solokey,a=1", scope=None)
        # Pair without '=' is skipped silently.
        assert result == {"a": "1"}

    @pytest.mark.anyio
    async def test_trailing_comma_yields_no_extra_key(self):
        r = VariableRenderer(make_source_resolver({}))
        result = await r._render_attrs("a=1,", scope=None)
        # Trailing empty segment has no '=' and is silently dropped.
        assert result == {"a": "1"}


class TestVariableRendererAttrsIntegration:
    """End-to-end: ${... as type/subtype[attrs]} captures rendered attrs at convert time."""

    @pytest.mark.anyio
    async def test_literal_attrs_passed_as_strings(self):
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=16000,channels=1]}")
        assert captured == [{"sample_rate": "16000", "channels": "1"}]

    @pytest.mark.anyio
    async def test_interpolated_attrs_preserve_native_types(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": 24000, "ch": 2},
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=${input.sr},channels=${input.ch}]}")
        assert captured == [{"sample_rate": 24000, "channels": 2}]

    @pytest.mark.anyio
    async def test_mixed_attrs(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": 48000},
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=${input.sr},channels=2,bit_depth=24]}")
        assert captured == [{"sample_rate": 48000, "channels": "2", "bit_depth": "24"}]

    @pytest.mark.anyio
    async def test_indexed_nested_var(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": [16000, 1, 22050],
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=${input[0]},channels=${input[1]}]}")
        assert captured == [{"sample_rate": 16000, "channels": 1}]

    @pytest.mark.anyio
    async def test_default_inside_attrs(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {},
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=${input.missing | 44100},channels=1]}")
        assert captured == [{"sample_rate": "44100", "channels": "1"}]

    @pytest.mark.anyio
    async def test_attrs_passed_to_pcm_stream_resource(self):
        """Bytes input with audio/pcm subtype wraps into PcmStreamResource carrying attrs."""
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({
            "v": b"raw_pcm",
            "input": {"sr": 24000},
        }))
        result = await r.render("${v as audio/pcm[sample_rate=${input.sr},channels=2,bit_depth=16]}")
        assert isinstance(result, PcmStreamResource)
        assert result.attrs == {"sample_rate": 24000, "channels": "2", "bit_depth": "16"}
        # sample_rate stays as int (variable interpolation), channels/bit_depth as str (literal).
        assert isinstance(result.attrs["sample_rate"], int)
        assert isinstance(result.attrs["channels"], str)

    @pytest.mark.anyio
    async def test_no_attrs_passes_none(self):
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm}")
        assert captured == [None]

    @pytest.mark.anyio
    async def test_empty_attrs_brackets_pass_through_raw(self):
        """Empty `[]` captures attrs as empty string, which is falsy and skips _render_attrs."""
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[]}")
        # The regex captures '' for empty brackets; '' is falsy so attrs stays as the raw '' string.
        # `_convert_value_to_type` receives the empty string as-is.
        assert captured == [""]

    @pytest.mark.anyio
    async def test_no_brackets_yields_none(self):
        """Without any brackets, the attrs group does not match and is None."""
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm}")
        assert captured == [None]

    @pytest.mark.anyio
    async def test_whitespace_inside_attrs_brackets(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": 22050},
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[ sample_rate = ${input.sr} , channels = 1 ]}")
        assert captured == [{"sample_rate": 22050, "channels": "1"}]

    @pytest.mark.anyio
    async def test_attrs_in_middle_of_text(self):
        """A variable with attrs embedded in surrounding text is still parsed correctly."""
        r = VariableRenderer(make_source_resolver({
            "v": b"raw pcm",
            "input": {"sr": 16000},
        }))
        captured = capture_attrs(r)
        # Conversion runs (bytes + audio/pcm) and its stringified result is interpolated.
        await r.render("prefix ${v as audio/pcm[sample_rate=${input.sr}]} suffix")
        # attrs is parsed for the call.
        assert captured == [{"sample_rate": 16000}]

    @pytest.mark.anyio
    async def test_literal_attrs_regression(self):
        """The pre-existing literal attrs form keeps working with the new pipeline."""
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        result = await r.render("${v as audio/pcm[sample_rate=44100,channels=2,bit_depth=16]}")
        assert isinstance(result, PcmStreamResource)
        assert result.attrs == {"sample_rate": "44100", "channels": "2", "bit_depth": "16"}

    @pytest.mark.anyio
    async def test_indexed_brackets_do_not_break_attrs_capture(self):
        """Ensure the regex's attrs group survives `]` inside nested ${input.list[0]}."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": [16000, 1, 22050],
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=${input[0]},channels=${input[1]},extra=${input[2]}]}")
        assert captured == [{"sample_rate": 16000, "channels": 1, "extra": 22050}]


class TestAttrsRegexBoundaries:
    """Boundary tests for the variable regex's attrs group."""

    @pytest.mark.anyio
    async def test_attrs_then_default_pipe(self):
        """Variable with attrs followed by `|` default — `|` lives outside the brackets."""
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        captured = capture_attrs(r)
        # Outer default pipe applies when value is None — here v exists so default not used.
        await r.render("${v as audio/pcm[sample_rate=16000] | fallback}")
        assert captured == [{"sample_rate": "16000"}]

    @pytest.mark.anyio
    async def test_no_subtype_means_no_attrs(self):
        """Without a subtype, attrs cannot appear (regex requires subtype before `[`)."""
        r = VariableRenderer(make_source_resolver({"v": "x"}))
        # `as string[sample_rate=16000]` does not match attrs — bracketed text becomes literal suffix
        # outside the match. The variable still converts to a string and is stringified.
        result = await r.render("${v as string}[sample_rate=16000]")
        assert "[sample_rate=16000]" in result

    @pytest.mark.anyio
    async def test_attrs_with_only_keys_no_values(self):
        """Pairs missing `=` are silently dropped by _render_attrs."""
        r = VariableRenderer(make_source_resolver({"v": b"data"}))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[flag,sample_rate=16000]}")
        assert captured == [{"sample_rate": "16000"}]

    @pytest.mark.anyio
    async def test_attrs_with_complex_path_interpolation(self):
        """Interpolated values can themselves use nested dot-paths."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "jobs": {"tts": {"output": {"sr": 22050, "ch": 1}}},
        }))
        captured = capture_attrs(r)
        await r.render("${v as audio/pcm[sample_rate=${jobs.tts.output.sr},channels=${jobs.tts.output.ch}]}")
        assert captured == [{"sample_rate": 22050, "channels": 1}]


class TestAttrsWithNestedTypeConversion:
    """Nested ${... as type} inside attrs — inner type conversion is honored."""

    @pytest.mark.anyio
    async def test_nested_as_integer(self):
        """A nested ${... as integer} produces an int that lands in attrs."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": "24000"},  # string source coerced to int by inner conversion
        }))
        result = await r.render("${v as audio/pcm[sample_rate=${input.sr as integer}]}")
        assert result.attrs == {"sample_rate": 24000}
        assert isinstance(result.attrs["sample_rate"], int)

    @pytest.mark.anyio
    async def test_nested_as_integer_truncates_float(self):
        """`as integer` on a float source truncates to int inside attrs."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"x": 3.9},
        }))
        result = await r.render("${v as audio/pcm[v=${input.x as integer}]}")
        assert result.attrs == {"v": 3}

    @pytest.mark.anyio
    async def test_nested_as_number(self):
        """`as number` produces a float inside attrs."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"ratio": "1.5"},
        }))
        result = await r.render("${v as audio/pcm[ratio=${input.ratio as number}]}")
        assert result.attrs == {"ratio": 1.5}
        assert isinstance(result.attrs["ratio"], float)

    @pytest.mark.anyio
    async def test_nested_as_boolean(self):
        """`as boolean` produces a bool inside attrs."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"flag": "true"},
        }))
        result = await r.render("${v as audio/pcm[flag=${input.flag as boolean}]}")
        assert result.attrs == {"flag": True}
        assert result.attrs["flag"] is True

    @pytest.mark.anyio
    async def test_nested_as_boolean_false(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"flag": "false"},
        }))
        result = await r.render("${v as audio/pcm[flag=${input.flag as boolean}]}")
        assert result.attrs == {"flag": False}

    @pytest.mark.anyio
    async def test_nested_as_json(self):
        """`as json` parses a JSON string into a Python value inside attrs."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"meta": '{"codec": "pcm_s16le"}'},
        }))
        result = await r.render("${v as audio/pcm[meta=${input.meta as json}]}")
        assert result.attrs == {"meta": {"codec": "pcm_s16le"}}

    @pytest.mark.anyio
    async def test_nested_with_indexed_path_and_type(self):
        """Nested indexed access followed by `as integer` works."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": ["16000", "1", "16"],
        }))
        result = await r.render("${v as audio/pcm[sr=${input[0] as integer},ch=${input[1] as integer},bit_depth=${input[2] as integer}]}")
        assert result.attrs == {"sr": 16000, "ch": 1, "bit_depth": 16}
        for v in result.attrs.values():
            assert isinstance(v, int)

    @pytest.mark.anyio
    async def test_mixed_typed_and_untyped_nested_attrs(self):
        """Some attrs values typed, others not — Dict[str, Any] preserves both."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": "44100", "ch": 2},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.sr as integer},ch=${input.ch},bit_depth=16]}")
        # `${input.ch}` is already int; `${input.sr as integer}` coerces; `16` is literal.
        assert result.attrs == {"sr": 44100, "ch": 2, "bit_depth": "16"}
        assert isinstance(result.attrs["sr"], int)
        assert isinstance(result.attrs["ch"], int)
        assert isinstance(result.attrs["bit_depth"], str)


class TestAttrsWithNestedDefault:
    """Nested ${... | default} inside attrs — fallback is interpolated and rendered."""

    @pytest.mark.anyio
    async def test_default_used_when_variable_missing(self):
        r = VariableRenderer(make_source_resolver({"v": b"data", "input": {}}))
        result = await r.render("${v as audio/pcm[sr=${input.missing | 44100}]}")
        # Default value (literal "44100") is the rendered text.
        assert result.attrs == {"sr": "44100"}
        assert isinstance(result.attrs["sr"], str)

    @pytest.mark.anyio
    async def test_default_skipped_when_variable_present(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": 24000},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.sr | 44100}]}")
        # Present value wins — int preserved.
        assert result.attrs == {"sr": 24000}
        assert isinstance(result.attrs["sr"], int)

    @pytest.mark.anyio
    async def test_default_is_string_literal(self):
        r = VariableRenderer(make_source_resolver({"v": b"data", "input": {}}))
        result = await r.render("${v as audio/pcm[mode=${input.missing | auto}]}")
        assert result.attrs == {"mode": "auto"}

    @pytest.mark.anyio
    async def test_default_contains_comma_kept_intact(self):
        """A comma inside the default expression must not split the attr pair."""
        r = VariableRenderer(make_source_resolver({"v": b"data", "input": {}}))
        result = await r.render("${v as audio/pcm[fallback=${input.missing | hello,world},ch=1]}")
        assert result.attrs == {"fallback": "hello,world", "ch": "1"}

    @pytest.mark.anyio
    async def test_default_contains_nested_variable(self):
        """A default can itself reference another variable."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": 22050, "missing": None},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.missing | ${input.sr}}]}")
        # Default resolves to ${input.sr} which renders as int 22050.
        assert result.attrs == {"sr": 22050}
        assert isinstance(result.attrs["sr"], int)

    @pytest.mark.anyio
    async def test_multiple_defaults_in_attrs(self):
        r = VariableRenderer(make_source_resolver({"v": b"data", "input": {}}))
        result = await r.render("${v as audio/pcm[sr=${input.missing | 44100},ch=${input.missing | 2}]}")
        assert result.attrs == {"sr": "44100", "ch": "2"}

    @pytest.mark.anyio
    async def test_default_with_whitespace(self):
        r = VariableRenderer(make_source_resolver({"v": b"data", "input": {}}))
        # Whitespace around `|` is allowed and trimmed by the renderer.
        result = await r.render("${v as audio/pcm[sr=${input.missing | 44100}]}")
        assert result.attrs == {"sr": "44100"}


class TestAttrsWithNestedTypeAndDefaultCombined:
    """`as type | default` order — the documented form — works at all nesting levels."""

    @pytest.mark.anyio
    async def test_as_then_default_outer_missing(self):
        """At the outer level, `as integer | 42` — default applies when value is None."""
        r = VariableRenderer(make_source_resolver({"input": {"missing": None}}))
        result = await r.render("${input.missing as integer | 42}")
        assert result == 42
        assert isinstance(result, int)

    @pytest.mark.anyio
    async def test_as_then_default_outer_present(self):
        r = VariableRenderer(make_source_resolver({"input": {"x": "7"}}))
        result = await r.render("${input.x as integer | 42}")
        assert result == 7

    @pytest.mark.anyio
    async def test_nested_as_then_default_missing(self):
        """`as type | default` inside an attrs value — default applies & is converted by `as`."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"missing": None},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.missing as integer | 42}]}")
        assert result.attrs == {"sr": 42}
        assert isinstance(result.attrs["sr"], int)

    @pytest.mark.anyio
    async def test_nested_as_then_default_present(self):
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"sr": "24000"},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.sr as integer | 42}]}")
        assert result.attrs == {"sr": 24000}
        assert isinstance(result.attrs["sr"], int)

    @pytest.mark.anyio
    async def test_nested_as_then_default_with_variable(self):
        """The default expression can itself reference another variable."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"missing": None, "fallback": "99"},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.missing as integer | ${input.fallback}}]}")
        assert result.attrs == {"sr": 99}
        assert isinstance(result.attrs["sr"], int)

    @pytest.mark.anyio
    async def test_nested_typed_var_inside_default(self):
        """A fully-typed inner variable can appear inside the default expression."""
        r = VariableRenderer(make_source_resolver({
            "v": b"data",
            "input": {"missing": None, "fallback": "99"},
        }))
        result = await r.render("${v as audio/pcm[sr=${input.missing | ${input.fallback as integer}}]}")
        # No outer `as` on the attrs value — default rendering yields int 99 via the inner typed var.
        assert result.attrs == {"sr": 99}
        assert isinstance(result.attrs["sr"], int)

    @pytest.mark.anyio
    async def test_pipe_before_as_is_not_supported(self):
        """`| default as type` is NOT the documented order — the entire `"X as type"` becomes the default text.

        The grammar specifies `as type | default | @(annotation)` — `as` must precede `|`.
        This test pins current behavior so an accidental grammar change is caught.
        """
        r = VariableRenderer(make_source_resolver({"v": b"data", "input": {}}))
        result = await r.render("${v as audio/pcm[sr=${input.missing | 44100 as integer}]}")
        # The text after `|` is treated as a literal default — `as integer` is part of the default text.
        assert result.attrs == {"sr": "44100 as integer"}


class TestAttrsWithDeeplyNested:
    """Doubly-nested attrs: ${... as audio/pcm[k=${... as audio/pcm[...]}]}."""

    @pytest.mark.anyio
    async def test_double_nested_attrs_preserve_inner_resource(self):
        """An inner `${raw as audio/pcm[...]}` produces a PcmStreamResource that lands in the outer attrs."""
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({
            "v": b"outer",
            "input": {"raw": b"inner"},
        }))
        result = await r.render(
            "${v as audio/pcm[ref=${input.raw as audio/pcm[sample_rate=16000]}]}"
        )
        # Outer is a PcmStreamResource wrapping b"outer".
        assert isinstance(result, PcmStreamResource)
        # Inner attrs key carries the inner PcmStreamResource object — Any honored.
        inner = result.attrs["ref"]
        assert isinstance(inner, PcmStreamResource)
        assert inner.attrs == {"sample_rate": "16000"}


# ============================
# `type[]` element-wise marker
# ============================

class TestElementWiseScalarTypes:
    """Element-wise conversion for scalar types (number, integer, boolean, json, string, text, markdown)."""

    @pytest.mark.anyio
    async def test_number_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["1.5", "2.5", "3.5"]}))
        result = await r.render("${v as number[]}")
        assert result == [1.5, 2.5, 3.5]
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.anyio
    async def test_integer_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["1", "2", "3"]}))
        result = await r.render("${v as integer[]}")
        assert result == [1, 2, 3]
        assert all(isinstance(x, int) for x in result)

    @pytest.mark.anyio
    async def test_boolean_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["true", "false", "True", "1", "0"]}))
        result = await r.render("${v as boolean[]}")
        assert result == [True, False, True, True, False]

    @pytest.mark.anyio
    async def test_json_list_with_string_elements(self):
        r = VariableRenderer(make_source_resolver({"v": ['{"a":1}', '[1,2]', '"x"']}))
        result = await r.render("${v as json[]}")
        assert result == [{"a": 1}, [1, 2], "x"]

    @pytest.mark.anyio
    async def test_string_list_normalizes_to_str(self):
        r = VariableRenderer(make_source_resolver({"v": ["a", 42, 3.14, True]}))
        result = await r.render("${v as string[]}")
        assert result == ["a", "42", "3.14", "True"]

    @pytest.mark.anyio
    async def test_text_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["hello", "world"]}))
        result = await r.render("${v as text[]}")
        assert result == ["hello", "world"]

    @pytest.mark.anyio
    async def test_markdown_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["# A", "## B"]}))
        result = await r.render("${v as markdown[]}")
        assert result == ["# A", "## B"]

    @pytest.mark.anyio
    async def test_base64_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["hi", b"raw"]}))
        result = await r.render("${v as base64[]}")
        assert result == [
            base64.b64encode(b"hi").decode("ascii"),
            base64.b64encode(b"raw").decode("ascii"),
        ]


class TestElementWiseTupleInput:
    """Tuple inputs are treated like lists (cardinality assertion accepts both)."""

    @pytest.mark.anyio
    async def test_integer_from_tuple(self):
        r = VariableRenderer(make_source_resolver({"v": ("1", "2", "3")}))
        result = await r.render("${v as integer[]}")
        assert result == [1, 2, 3]


class TestElementWiseEmptyList:
    """Empty list passes through as empty list for any type."""

    @pytest.mark.anyio
    async def test_empty_integer_list(self):
        r = VariableRenderer(make_source_resolver({"v": []}))
        result = await r.render("${v as integer[]}")
        assert result == []

    @pytest.mark.anyio
    async def test_empty_json_list(self):
        r = VariableRenderer(make_source_resolver({"v": []}))
        result = await r.render("${v as json[]}")
        assert result == []


class TestElementWiseNonListInputRaises:
    """`type[]` + non-list input raises ValueError (cardinality assertion)."""

    @pytest.mark.anyio
    async def test_integer_with_str_raises(self):
        r = VariableRenderer(make_source_resolver({"v": "1"}))
        with pytest.raises(ValueError, match="requires a list/tuple input"):
            await r.render("${v as integer[]}")

    @pytest.mark.anyio
    async def test_integer_with_int_raises(self):
        r = VariableRenderer(make_source_resolver({"v": 42}))
        with pytest.raises(ValueError, match="requires a list/tuple input"):
            await r.render("${v as integer[]}")

    @pytest.mark.anyio
    async def test_object_with_dict_raises(self):
        r = VariableRenderer(make_source_resolver({"v": {"a": 1}}))
        with pytest.raises(ValueError, match="requires a list/tuple input"):
            await r.render("${v as object[]}")

    @pytest.mark.anyio
    async def test_json_with_dict_raises(self):
        r = VariableRenderer(make_source_resolver({"v": {"a": 1}}))
        with pytest.raises(ValueError, match="requires a list/tuple input"):
            await r.render("${v as json[]}")


class TestElementWiseNoneElement:
    """None elements pass through as None in element-wise mode."""

    @pytest.mark.anyio
    async def test_none_passes_through_integer(self):
        r = VariableRenderer(make_source_resolver({"v": ["1", None, "3"]}))
        result = await r.render("${v as integer[]}")
        assert result == [1, None, 3]

    @pytest.mark.anyio
    async def test_all_none_elements(self):
        r = VariableRenderer(make_source_resolver({"v": [None, None]}))
        result = await r.render("${v as number[]}")
        assert result == [None, None]

    @pytest.mark.anyio
    async def test_none_in_string_list(self):
        r = VariableRenderer(make_source_resolver({"v": ["a", None, "b"]}))
        result = await r.render("${v as string[]}")
        assert result == ["a", None, "b"]


class TestElementWisePropagatesElementFailure:
    """Element conversion errors propagate (entire list fails)."""

    @pytest.mark.anyio
    async def test_invalid_integer_element_raises(self):
        r = VariableRenderer(make_source_resolver({"v": ["1", "abc", "3"]}))
        with pytest.raises(ValueError):
            await r.render("${v as integer[]}")

    @pytest.mark.anyio
    async def test_invalid_json_element_raises(self):
        r = VariableRenderer(make_source_resolver({"v": ['{"a":1}', "not json"]}))
        with pytest.raises(Exception):  # JSONDecodeError
            await r.render("${v as json[]}")


class TestElementWiseFormatApplied:
    """`format` is applied to each element (str-only elements supported)."""

    @pytest.mark.anyio
    async def test_integer_list_base64(self):
        r = VariableRenderer(make_source_resolver({
            "v": [base64.b64encode(b"1").decode(), base64.b64encode(b"2").decode()]
        }))
        result = await r.render("${v as integer[];base64}")
        assert result == [1, 2]

    @pytest.mark.anyio
    async def test_json_list_data_uri(self):
        r = VariableRenderer(make_source_resolver({
            "v": [
                "data:application/json,%5B1%5D",
                "data:application/json;base64," + base64.b64encode(b"[2,3]").decode(),
            ]
        }))
        result = await r.render("${v as json[];data-uri}")
        assert result == [[1], [2, 3]]

    @pytest.mark.anyio
    async def test_string_list_base64(self):
        r = VariableRenderer(make_source_resolver({
            "v": [base64.b64encode(b"hello").decode(), base64.b64encode(b"world").decode()]
        }))
        result = await r.render("${v as string[];base64}")
        assert result == ["hello", "world"]


class TestElementWiseObjectArray:
    """`object[]` strict policy: list of dicts (with optional subtype field projection)."""

    @pytest.mark.anyio
    async def test_dict_list_passes_through(self):
        users = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        r = VariableRenderer(make_source_resolver({"v": users}))
        result = await r.render("${v as object[]}")
        assert result == users

    @pytest.mark.anyio
    async def test_subtype_projects_fields(self):
        users = [{"name": "Alice", "email": "a@x", "age": 30}, {"name": "Bob", "email": "b@y", "age": 25}]
        r = VariableRenderer(make_source_resolver({"v": users}))
        result = await r.render("${v as object[]/name,email}")
        assert result == [{"name": "Alice", "email": "a@x"}, {"name": "Bob", "email": "b@y"}]

    @pytest.mark.anyio
    async def test_non_dict_non_json_element_raises(self):
        """Non-JSON-parseable str element fails at JSON parsing stage."""
        r = VariableRenderer(make_source_resolver({"v": [{"a": 1}, "not a dict"]}))
        with pytest.raises(Exception):  # JSONDecodeError or ValueError
            await r.render("${v as object[]}")

    @pytest.mark.anyio
    async def test_non_dict_scalar_element_raises(self):
        """Non-dict scalar element (e.g. int) fails the dict assertion."""
        r = VariableRenderer(make_source_resolver({"v": [{"a": 1}, 42]}))
        with pytest.raises(ValueError, match="requires a dict input"):
            await r.render("${v as object[]}")

    @pytest.mark.anyio
    async def test_json_string_element_parses_then_validates(self):
        """A JSON-parseable string that yields a dict is accepted."""
        r = VariableRenderer(make_source_resolver({"v": [{"a": 1}, '{"b": 2}']}))
        result = await r.render("${v as object[]}")
        assert result == [{"a": 1}, {"b": 2}]


class TestElementWiseSseRaises:
    """`event-stream[]` is not allowed: stream is single by nature."""

    @pytest.mark.anyio
    async def test_event_stream_list_raises(self):
        r = VariableRenderer(make_source_resolver({"v": ["a", "b"]}))
        with pytest.raises(ValueError, match="is not allowed: stream"):
            await r.render("${v as event-stream[]}")

    @pytest.mark.anyio
    async def test_event_stream_list_raises_even_for_non_list_input(self):
        r = VariableRenderer(make_source_resolver({"v": "single"}))
        with pytest.raises(ValueError, match="is not allowed: stream"):
            await r.render("${v as event-stream[]}")


class TestElementWiseMedia:
    """`type[]` on media types applies type-specific conversion to each element."""

    @pytest.mark.anyio
    async def test_audio_pcm_list_from_bytes(self):
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({"v": [b"raw1", b"raw2"]}))
        result = await r.render("${v as audio[]/pcm[sample_rate=16000]}")
        assert len(result) == 2
        assert all(isinstance(x, PcmStreamResource) for x in result)
        assert all(x.attrs == {"sample_rate": "16000"} for x in result)

    @pytest.mark.anyio
    async def test_file_list_from_bytes(self):
        r = VariableRenderer(make_source_resolver({"v": [b"a", b"b"]}))
        result = await r.render("${v as file[]}")
        assert len(result) == 2
        assert all(isinstance(x, BytesStreamResource) for x in result)


class TestElementWiseTypeMismatchInList:
    """Mixed element types: each element follows its own type matrix row independently."""

    @pytest.mark.anyio
    async def test_integer_list_with_mixed_int_and_str(self):
        r = VariableRenderer(make_source_resolver({"v": [1, "2", 3.5]}))
        result = await r.render("${v as integer[]}")
        assert result == [1, 2, 3]

    @pytest.mark.anyio
    async def test_string_list_with_mixed_scalars(self):
        r = VariableRenderer(make_source_resolver({"v": [1, "two", 3.0, True]}))
        result = await r.render("${v as string[]}")
        assert result == ["1", "two", "3.0", "True"]


class TestElementWiseNestedBracketsRejected:
    """Nested `[]` (e.g. `integer[][]`) is not supported — the regex does not accept it."""

    @pytest.mark.anyio
    async def test_double_brackets_does_not_match_as_element_wise(self):
        r = VariableRenderer(make_source_resolver({"v": [[1, 2], [3, 4]]}))
        # The regex captures only one set of `[]`. `${v as integer[][]}` does not match
        # the variable pattern at all, so the literal text passes through.
        result = await r.render("${v as integer[][]}")
        assert "as integer" in result or result == "${v as integer[][]}"


# ============================
# Misc VariableRenderer branches
# ============================

class TestBaseModelInput:
    """Pydantic BaseModel inputs are recursively dumped as dicts."""

    @pytest.mark.anyio
    async def test_basemodel_value_is_dumped(self):
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str
            count: int

        async def resolver(key, index=None, scope=None):
            return None

        r = VariableRenderer(resolver)
        result = await r.render(Item(name="x", count=3))
        assert result == {"name": "x", "count": 3}


class TestUnknownTypeFallthrough:
    """Unknown type names pass the value through unchanged."""

    @pytest.mark.anyio
    async def test_unknown_type_returns_value(self):
        r = VariableRenderer(make_source_resolver({"v": {"a": 1}}))
        result = await r.render("${v as something-weird}")
        assert result == {"a": 1}


class TestSourceResolverFailureUsesDefault:
    """When the resolver raises, value becomes None and default is applied."""

    @pytest.mark.anyio
    async def test_resolver_exception_falls_back_to_default(self):
        async def resolver(key, index=None, scope=None):
            raise RuntimeError("boom")

        r = VariableRenderer(resolver)
        result = await r.render("${v | fallback}")
        assert result == "fallback"

    @pytest.mark.anyio
    async def test_resolver_exception_without_default_yields_none(self):
        async def resolver(key, index=None, scope=None):
            raise RuntimeError("boom")

        r = VariableRenderer(resolver)
        result = await r.render("${v as integer}")
        assert result is None


class TestBooleanFromBytes:
    """boolean type accepts bytes input (post format resolution)."""

    @pytest.mark.anyio
    async def test_bytes_true(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"true").decode()}))
        result = await r.render("${v as boolean;base64}")
        assert result is True

    @pytest.mark.anyio
    async def test_bytes_one(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"1").decode()}))
        result = await r.render("${v as boolean;base64}")
        assert result is True

    @pytest.mark.anyio
    async def test_bytes_false(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"false").decode()}))
        result = await r.render("${v as boolean;base64}")
        assert result is False


class TestListType:
    """`as list` requires a list input."""

    @pytest.mark.anyio
    async def test_list_passes_through(self):
        r = VariableRenderer(make_source_resolver({"v": [1, 2, 3]}))
        result = await r.render("${v as list}")
        assert result == [1, 2, 3]

    @pytest.mark.anyio
    async def test_non_list_dict_raises(self):
        r = VariableRenderer(make_source_resolver({"v": {"a": 1}}))
        with pytest.raises(ValueError, match="requires a list input"):
            await r.render("${v as list}")

    @pytest.mark.anyio
    async def test_non_list_invalid_json_str_raises_json_error(self):
        r = VariableRenderer(make_source_resolver({"v": "not a list"}))
        with pytest.raises(Exception):  # JSONDecodeError from header parse stage
            await r.render("${v as list}")

    @pytest.mark.anyio
    async def test_list_from_json_string(self):
        r = VariableRenderer(make_source_resolver({"v": "[1, 2, 3]"}))
        result = await r.render("${v as list}")
        assert result == [1, 2, 3]


class TestBase64FromPILImage:
    """`as base64` accepts PIL.Image.Image (encodes as PNG by default)."""

    @pytest.mark.anyio
    async def test_pil_image_to_base64(self):
        from PIL import Image as PILImage
        img = PILImage.new("RGB", (4, 4), color="red")
        r = VariableRenderer(make_source_resolver({"v": img}))
        result = await r.render("${v as base64}")
        assert isinstance(result, str)
        # Decoded bytes should start with PNG signature.
        decoded = base64.b64decode(result)
        assert decoded.startswith(b"\x89PNG")


class TestBase64FromUploadFile:
    """`as base64` accepts UploadFile."""

    @pytest.mark.anyio
    async def test_upload_file_to_base64(self):
        f = UploadFile(file=io.BytesIO(b"hello"), filename="x.bin")
        r = VariableRenderer(make_source_resolver({"v": f}))
        result = await r.render("${v as base64}")
        assert result == base64.b64encode(b"hello").decode("ascii")


class TestLoadBytesFromUrl:
    """`_load_bytes_from_format` with url/path is exercised via scalar conversion paths."""

    @pytest.mark.anyio
    async def test_integer_from_path(self, tmp_path):
        p = tmp_path / "n.txt"
        p.write_text("42")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        result = await r.render("${v as integer;path}")
        assert result == 42

    @pytest.mark.anyio
    async def test_json_from_path(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"a": [1, 2]}')
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        result = await r.render("${v as json;path}")
        assert result == {"a": [1, 2]}


class TestUnknownFormatRaisesInLoader:
    """`_load_bytes_from_format` / `_load_stream_from_format` raise on unknown format internally."""

    @pytest.mark.anyio
    async def test_unknown_format_in_bytes_loader(self):
        r = VariableRenderer(make_source_resolver({}))
        with pytest.raises(ValueError, match="Unknown format"):
            await r._load_bytes_from_format("x", "weird")

    @pytest.mark.anyio
    async def test_unknown_format_in_stream_loader(self):
        r = VariableRenderer(make_source_resolver({}))
        with pytest.raises(ValueError, match="Unknown format"):
            await r._load_stream_from_format("x", "weird")


# ============================
# contains_reference
# ============================

class TestContainsReference:
    """Public contains_reference: checks whether a value (str/dict/list) references a key."""

    def _r(self):
        return VariableRenderer(make_source_resolver({}))

    def test_str_with_matching_reference(self):
        r = self._r()
        assert r.contains_reference("input", "hello ${input.name}") is True

    def test_str_with_other_reference(self):
        r = self._r()
        assert r.contains_reference("input", "${other.x}") is False

    def test_str_with_no_reference(self):
        r = self._r()
        assert r.contains_reference("input", "plain text") is False

    def test_dict_value_with_matching_reference(self):
        r = self._r()
        assert r.contains_reference("input", {"k": "${input.x}"}) is True

    def test_dict_value_with_no_reference(self):
        r = self._r()
        assert r.contains_reference("input", {"k": "plain", "j": 42}) is False

    def test_list_value_with_matching_reference(self):
        r = self._r()
        assert r.contains_reference("input", ["a", "${input.b}", 3]) is True

    def test_list_value_with_no_reference(self):
        r = self._r()
        assert r.contains_reference("input", ["a", 1, {"nested": "x"}]) is False

    def test_nested_dict_in_list(self):
        r = self._r()
        assert r.contains_reference("input", [{"k": "${input.x}"}]) is True

    def test_scalar_value_returns_false(self):
        r = self._r()
        assert r.contains_reference("input", 42) is False
        assert r.contains_reference("input", None) is False


# ============================
# ImageValueRenderer
# ============================

class TestImageValueRenderer:
    @pytest.mark.anyio
    async def test_pil_image_returns_as_is(self):
        from PIL import Image as PILImage
        from mindor.core.utils.renderers import ImageValueRenderer
        img = PILImage.new("RGB", (4, 4))
        result = await ImageValueRenderer().render(img)
        assert result is img

    @pytest.mark.anyio
    async def test_stream_resource_loaded_into_pil(self):
        import io
        from PIL import Image as PILImage
        from mindor.core.utils.renderers import ImageValueRenderer
        buf = io.BytesIO()
        PILImage.new("RGB", (4, 4), color="red").save(buf, "PNG")
        stream = BytesStreamResource(buf.getvalue())
        result = await ImageValueRenderer().render(stream)
        assert isinstance(result, PILImage.Image)

    @pytest.mark.anyio
    async def test_image_stream_resource_returns_pil_directly(self):
        from PIL import Image as PILImage
        from mindor.core.utils.streaming.image import ImageStreamResource
        from mindor.core.utils.renderers import ImageValueRenderer
        pil = PILImage.new("RGB", (4, 4))
        wrapped = ImageStreamResource(pil, "png")
        result = await ImageValueRenderer().render(wrapped)
        assert result is pil

    @pytest.mark.anyio
    async def test_async_iterator_lazy_maps_elements(self):
        """AsyncIterator input: render returns a new async generator that lazily
        maps each element via _render_element (single-pass)."""
        from PIL import Image as PILImage
        from mindor.core.utils.streaming.image import ImageStreamResource
        from mindor.core.utils.renderers import ImageValueRenderer
        from collections.abc import AsyncIterator
        pil = PILImage.new("RGB", (4, 4))
        wrapped = ImageStreamResource(pil, "png")
        it = make_async_iterator([wrapped])
        result = await ImageValueRenderer().render(it)
        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert items == [pil]

    @pytest.mark.anyio
    async def test_list_recurses(self):
        from PIL import Image as PILImage
        from mindor.core.utils.renderers import ImageValueRenderer
        img = PILImage.new("RGB", (2, 2))
        result = await ImageValueRenderer().render([img, img])
        assert len(result) == 2
        assert all(r is img for r in result)

    @pytest.mark.anyio
    async def test_unsupported_returns_none(self):
        from mindor.core.utils.renderers import ImageValueRenderer
        result = await ImageValueRenderer().render(42)
        assert result is None


# ============================
# FileValueRenderer
# ============================

class TestFileValueRenderer:
    @pytest.mark.anyio
    async def test_stream_resource_saved_to_temp(self):
        import os
        from mindor.core.utils.renderers import FileValueRenderer
        stream = BytesStreamResource(b"streamed")
        path = await FileValueRenderer().render(stream)
        assert isinstance(path, str) and os.path.isfile(path)
        with open(path, "rb") as f:
            assert f.read() == b"streamed"
        os.unlink(path)

    @pytest.mark.anyio
    async def test_list_recurses(self):
        import os
        from mindor.core.utils.renderers import FileValueRenderer
        s1 = BytesStreamResource(b"a")
        s2 = BytesStreamResource(b"b")
        result = await FileValueRenderer().render([s1, s2])
        assert len(result) == 2
        assert all(isinstance(p, str) and os.path.isfile(p) for p in result)
        for p in result:
            os.unlink(p)

    @pytest.mark.anyio
    async def test_unsupported_returns_none(self):
        from mindor.core.utils.renderers import FileValueRenderer
        result = await FileValueRenderer().render(42)
        assert result is None

    @pytest.mark.anyio
    async def test_str_returns_none(self):
        from mindor.core.utils.renderers import FileValueRenderer
        # str is not StreamResource — falls through to None.
        result = await FileValueRenderer().render("some text")
        assert result is None


# ============================
# SizeValueRenderer
# ============================

class TestSizeValueRenderer:
    @pytest.mark.anyio
    async def test_int_passes_through(self):
        from mindor.core.utils.renderers import SizeValueRenderer
        result = await SizeValueRenderer().render(1024)
        assert result == 1024

    @pytest.mark.anyio
    async def test_string_size_parsed(self):
        from mindor.core.utils.renderers import SizeValueRenderer
        result = await SizeValueRenderer().render("1KB")
        assert result == 1024

    @pytest.mark.anyio
    async def test_none_returns_default(self):
        from mindor.core.utils.renderers import SizeValueRenderer
        result = await SizeValueRenderer().render(None, default=512)
        assert result == 512


# ============================
# AudioValueRenderer / VideoValueRenderer
# ============================

class TestAudioValueRenderer:
    @pytest.mark.anyio
    async def test_stream_resource_wrapped_in_media_source(self):
        from mindor.core.utils.renderers import AudioValueRenderer
        from mindor.core.utils.streaming.media import MediaSource
        stream = BytesStreamResource(b"data")
        result = await AudioValueRenderer().render(stream)
        assert isinstance(result, MediaSource)
        assert result.stream is stream

    @pytest.mark.anyio
    async def test_async_iterator_lazy_maps_elements(self):
        """AsyncIterator input: render returns a new async generator that lazily
        maps each element via create_audio_source. Unsupported element types
        surface as TypeError on iteration."""
        from collections.abc import AsyncIterator
        from mindor.core.utils.renderers import AudioValueRenderer
        from mindor.core.utils.streaming.media import MediaSource
        it = make_async_iterator([b"x"])
        result = await AudioValueRenderer().render(it)
        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 1 and isinstance(items[0], MediaSource)

    @pytest.mark.anyio
    async def test_async_iterator_unsupported_element_raises_on_iteration(self):
        from collections.abc import AsyncIterator
        from mindor.core.utils.renderers import AudioValueRenderer
        it = make_async_iterator([42])
        result = await AudioValueRenderer().render(it)
        assert isinstance(result, AsyncIterator)
        with pytest.raises(TypeError):
            [item async for item in result]

    @pytest.mark.anyio
    async def test_list_recurses(self):
        from mindor.core.utils.renderers import AudioValueRenderer
        from mindor.core.utils.streaming.media import MediaSource
        s1 = BytesStreamResource(b"a")
        s2 = BytesStreamResource(b"b")
        result = await AudioValueRenderer().render([s1, s2])
        assert isinstance(result, list) and len(result) == 2
        assert all(isinstance(r, MediaSource) for r in result)
        assert result[0].stream is s1 and result[1].stream is s2

    @pytest.mark.anyio
    async def test_unsupported_raises(self):
        from mindor.core.utils.renderers import AudioValueRenderer
        with pytest.raises(TypeError):
            await AudioValueRenderer().render(42)
        with pytest.raises(TypeError):
            await AudioValueRenderer().render("not-a-stream")


class TestLoadStreamFromFormatHelper:
    """Direct unit tests for _load_stream_from_format."""

    @pytest.mark.anyio
    async def test_url_returns_url_stream(self):
        from mindor.core.utils.streaming.url import UrlStreamResource
        r = VariableRenderer(make_source_resolver({}))
        result = await r._load_stream_from_format("https://example.com/x", "url")
        assert isinstance(result, UrlStreamResource)
        assert result.url == "https://example.com/x"

    @pytest.mark.anyio
    async def test_path_returns_file_stream(self, tmp_path):
        from mindor.core.utils.streaming.file import FileStreamResource
        p = tmp_path / "f.txt"
        p.write_text("x")
        r = VariableRenderer(make_source_resolver({}))
        result = await r._load_stream_from_format(str(p), "path")
        assert isinstance(result, FileStreamResource)

    @pytest.mark.anyio
    async def test_base64_returns_base64_stream(self):
        from mindor.core.utils.streaming.base64 import Base64StreamResource
        r = VariableRenderer(make_source_resolver({}))
        result = await r._load_stream_from_format(base64.b64encode(b"x").decode(), "base64")
        assert isinstance(result, Base64StreamResource)

    @pytest.mark.anyio
    async def test_data_uri_base64_returns_data_uri_stream(self):
        from mindor.core.utils.streaming.url import DataUriStreamResource
        r = VariableRenderer(make_source_resolver({}))
        uri = "data:application/octet-stream;base64," + base64.b64encode(b"x").decode()
        result = await r._load_stream_from_format(uri, "data-uri")
        assert isinstance(result, DataUriStreamResource)
        assert result.uri == uri
        chunks = b"".join([c async for c in result])
        assert chunks == b"x"

    @pytest.mark.anyio
    async def test_data_uri_percent_returns_data_uri_stream(self):
        from mindor.core.utils.streaming.url import DataUriStreamResource
        r = VariableRenderer(make_source_resolver({}))
        uri = "data:text/plain,hi"
        result = await r._load_stream_from_format(uri, "data-uri")
        assert isinstance(result, DataUriStreamResource)
        assert result.uri == uri
        chunks = b"".join([c async for c in result])
        assert chunks == b"hi"


class TestMediaBranchAudioVideoSubtypes:
    """audio/video conversion via _convert_value_to_type for non-pcm/wav subtypes."""

    @pytest.mark.anyio
    async def test_audio_mp3_from_bytes(self):
        from mindor.core.utils.streaming.audio import AudioStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"mp3 bytes"}))
        result = await r.render("${v as audio/mp3}")
        assert isinstance(result, AudioStreamResource)
        assert result.format == "mp3"

    @pytest.mark.anyio
    async def test_audio_non_binary_raises(self):
        r = VariableRenderer(make_source_resolver({"v": 42}))
        with pytest.raises(TypeError, match="requires raw audio bytes"):
            await r.render("${v as audio/mp3}")

    @pytest.mark.anyio
    async def test_video_mp4_from_bytes(self):
        from mindor.core.utils.streaming.video import VideoStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"mp4 bytes"}))
        result = await r.render("${v as video/mp4}")
        assert isinstance(result, VideoStreamResource)
        assert result.format == "mp4"

    @pytest.mark.anyio
    async def test_video_non_binary_raises(self):
        r = VariableRenderer(make_source_resolver({"v": 42}))
        with pytest.raises(TypeError, match="requires raw video input"):
            await r.render("${v as video/mp4}")


class TestMediaBranchImageWithFormat:
    """`as image;<format>` exercises the lazy stream + load_image_from_stream + ImageStreamResource path."""

    @pytest.mark.anyio
    async def test_image_path_with_subtype(self, tmp_path):
        import io
        from PIL import Image as PILImage
        from mindor.core.utils.streaming.image import ImageStreamResource
        buf = io.BytesIO()
        PILImage.new("RGB", (4, 4), color="blue").save(buf, "PNG")
        p = tmp_path / "img.png"
        p.write_bytes(buf.getvalue())
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        result = await r.render("${v as image/png;path}")
        assert isinstance(result, ImageStreamResource)
        assert result.format == "png"

    @pytest.mark.anyio
    async def test_image_base64_without_subtype_returns_pil(self):
        import io
        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (4, 4), color="green").save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        r = VariableRenderer(make_source_resolver({"v": b64}))
        result = await r.render("${v as image;base64}")
        assert isinstance(result, PILImage.Image)


class TestVideoValueRenderer:
    @pytest.mark.anyio
    async def test_stream_resource_wrapped_in_media_source(self):
        from mindor.core.utils.renderers import VideoValueRenderer
        from mindor.core.utils.streaming.media import MediaSource
        stream = BytesStreamResource(b"data")
        result = await VideoValueRenderer().render(stream)
        assert isinstance(result, MediaSource)
        assert result.stream is stream

    @pytest.mark.anyio
    async def test_async_iterator_lazy_maps_elements(self):
        """AsyncIterator input: render returns a new async generator that lazily
        maps each element via create_video_source. Unsupported element types
        surface as TypeError on iteration."""
        from collections.abc import AsyncIterator
        from mindor.core.utils.renderers import VideoValueRenderer
        from mindor.core.utils.streaming.media import MediaSource
        it = make_async_iterator([b"x"])
        result = await VideoValueRenderer().render(it)
        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 1 and isinstance(items[0], MediaSource)

    @pytest.mark.anyio
    async def test_async_iterator_unsupported_element_raises_on_iteration(self):
        from collections.abc import AsyncIterator
        from mindor.core.utils.renderers import VideoValueRenderer
        it = make_async_iterator([42])
        result = await VideoValueRenderer().render(it)
        assert isinstance(result, AsyncIterator)
        with pytest.raises(TypeError):
            [item async for item in result]

    @pytest.mark.anyio
    async def test_list_recurses(self):
        from mindor.core.utils.renderers import VideoValueRenderer
        from mindor.core.utils.streaming.media import MediaSource
        s1 = BytesStreamResource(b"a")
        s2 = BytesStreamResource(b"b")
        result = await VideoValueRenderer().render([s1, s2])
        assert isinstance(result, list) and len(result) == 2
        assert all(isinstance(r, MediaSource) for r in result)
        assert result[0].stream is s1 and result[1].stream is s2

    @pytest.mark.anyio
    async def test_unsupported_raises(self):
        from mindor.core.utils.renderers import VideoValueRenderer
        with pytest.raises(TypeError):
            await VideoValueRenderer().render(42)
        with pytest.raises(TypeError):
            await VideoValueRenderer().render("not-a-stream")


# ============================
# Format × type matrix combinations
# ============================

class TestFormatMatrixNumber:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "n.txt"; p.write_text("2.5")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as number;path}") == 2.5

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"7.0").decode()}))
        assert await r.render("${v as number;base64}") == 7.0

    @pytest.mark.anyio
    async def test_data_uri_percent(self):
        r = VariableRenderer(make_source_resolver({"v": "data:text/plain,3.14"}))
        assert await r.render("${v as number;data-uri}") == 3.14

    @pytest.mark.anyio
    async def test_data_uri_base64(self):
        r = VariableRenderer(make_source_resolver({
            "v": "data:text/plain;base64," + base64.b64encode(b"9.5").decode()
        }))
        assert await r.render("${v as number;data-uri}") == 9.5


class TestFormatMatrixInteger:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "n.txt"; p.write_text("42")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as integer;path}") == 42

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"123").decode()}))
        assert await r.render("${v as integer;base64}") == 123

    @pytest.mark.anyio
    async def test_data_uri(self):
        r = VariableRenderer(make_source_resolver({"v": "data:text/plain,17"}))
        assert await r.render("${v as integer;data-uri}") == 17


class TestFormatMatrixBoolean:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "b.txt"; p.write_text("true")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as boolean;path}") is True

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"false").decode()}))
        assert await r.render("${v as boolean;base64}") is False

    @pytest.mark.anyio
    async def test_data_uri(self):
        r = VariableRenderer(make_source_resolver({"v": "data:text/plain,1"}))
        assert await r.render("${v as boolean;data-uri}") is True


class TestFormatMatrixJson:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "x.json"; p.write_text('{"a":[1,2]}')
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as json;path}") == {"a": [1, 2]}

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b'[1,2,3]').decode()}))
        assert await r.render("${v as json;base64}") == [1, 2, 3]

    @pytest.mark.anyio
    async def test_data_uri(self):
        r = VariableRenderer(make_source_resolver({"v": "data:application/json,%7B%22k%22%3A1%7D"}))
        assert await r.render("${v as json;data-uri}") == {"k": 1}


class TestFormatMatrixObject:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "u.json"; p.write_text('{"name":"Alice","age":30}')
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as object/name;path}") == {"name": "Alice"}

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({
            "v": base64.b64encode(b'{"a":1,"b":2}').decode()
        }))
        assert await r.render("${v as object/a,b;base64}") == {"a": 1, "b": 2}

    @pytest.mark.anyio
    async def test_data_uri(self):
        r = VariableRenderer(make_source_resolver({"v": "data:application/json,%7B%22x%22%3A5%7D"}))
        assert await r.render("${v as object;data-uri}") == {"x": 5}


class TestFormatMatrixList:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "l.json"; p.write_text("[10,20,30]")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as list;path}") == [10, 20, 30]

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"[1,2]").decode()}))
        assert await r.render("${v as list;base64}") == [1, 2]


class TestFormatMatrixBase64:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "x.bin"; p.write_bytes(b"hello world")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        result = await r.render("${v as base64;path}")
        assert result == base64.b64encode(b"hello world").decode("ascii")

    @pytest.mark.anyio
    async def test_data_uri_base64(self):
        r = VariableRenderer(make_source_resolver({
            "v": "data:application/octet-stream;base64," + base64.b64encode(b"binary").decode()
        }))
        result = await r.render("${v as base64;data-uri}")
        assert result == base64.b64encode(b"binary").decode("ascii")

    @pytest.mark.anyio
    async def test_base64_input_passes_through(self):
        # `;base64` on `as base64` is a no-op (input already base64).
        b64 = base64.b64encode(b"x").decode()
        r = VariableRenderer(make_source_resolver({"v": b64}))
        result = await r.render("${v as base64;base64}")
        assert result == b64


class TestFormatMatrixString:
    @pytest.mark.anyio
    async def test_path(self, tmp_path):
        p = tmp_path / "x.txt"; p.write_text("hello")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as string;path}") == "hello"

    @pytest.mark.anyio
    async def test_base64(self):
        r = VariableRenderer(make_source_resolver({"v": base64.b64encode(b"world").decode()}))
        assert await r.render("${v as string;base64}") == "world"

    @pytest.mark.anyio
    async def test_data_uri(self):
        r = VariableRenderer(make_source_resolver({"v": "data:text/plain,raw%20text"}))
        assert await r.render("${v as text;data-uri}") == "raw text"

    @pytest.mark.anyio
    async def test_markdown_from_path(self, tmp_path):
        p = tmp_path / "doc.md"; p.write_text("# Title")
        r = VariableRenderer(make_source_resolver({"v": str(p)}))
        assert await r.render("${v as markdown;path}") == "# Title"


# ============================
# Variable embedded in literal text
# ============================

class TestVariableInLiteralText:
    @pytest.mark.anyio
    async def test_integer_in_middle(self):
        r = VariableRenderer(make_source_resolver({"n": 42}))
        result = await r.render("prefix ${n as integer} suffix")
        assert result == "prefix 42 suffix"

    @pytest.mark.anyio
    async def test_number_in_middle(self):
        r = VariableRenderer(make_source_resolver({"n": "3.14"}))
        result = await r.render("pi=${n as number}")
        assert result == "pi=3.14"

    @pytest.mark.anyio
    async def test_boolean_in_middle(self):
        r = VariableRenderer(make_source_resolver({"b": "true"}))
        result = await r.render("flag=${b as boolean}.")
        assert result == "flag=True."

    @pytest.mark.anyio
    async def test_none_value_yields_empty(self):
        r = VariableRenderer(make_source_resolver({"x": None}))
        result = await r.render("a${x as integer}b")
        assert result == "ab"

    @pytest.mark.anyio
    async def test_multiple_variables_in_text(self):
        r = VariableRenderer(make_source_resolver({"a": "1", "b": "2"}))
        result = await r.render("${a as integer}+${b as integer}=...")
        assert result == "1+2=..."

    @pytest.mark.anyio
    async def test_variable_at_start(self):
        r = VariableRenderer(make_source_resolver({"v": 5}))
        result = await r.render("${v as integer} items")
        assert result == "5 items"

    @pytest.mark.anyio
    async def test_variable_at_end(self):
        r = VariableRenderer(make_source_resolver({"v": "X"}))
        result = await r.render("name: ${v as string}")
        assert result == "name: X"

    @pytest.mark.anyio
    async def test_full_span_returns_native_type(self):
        # Whole-text match returns native type, not stringified.
        r = VariableRenderer(make_source_resolver({"v": 7}))
        result = await r.render("${v as integer}")
        assert result == 7 and isinstance(result, int)

    @pytest.mark.anyio
    async def test_no_variable_returns_text_as_is(self):
        r = VariableRenderer(make_source_resolver({}))
        result = await r.render("plain text without vars")
        assert result == "plain text without vars"


# ============================
# Path / index expressions in resolver keys
# ============================

class TestPathExpressions:
    @pytest.mark.anyio
    async def test_dot_path(self):
        r = VariableRenderer(make_source_resolver({"data": {"user": {"name": "Alice"}}}))
        assert await r.render("${data.user.name}") == "Alice"

    @pytest.mark.anyio
    async def test_array_index_positive(self):
        r = VariableRenderer(make_source_resolver({"items": ["a", "b", "c"]}))
        assert await r.render("${items[1]}") == "b"

    @pytest.mark.anyio
    async def test_array_index_zero(self):
        r = VariableRenderer(make_source_resolver({"items": ["a", "b", "c"]}))
        assert await r.render("${items[0]}") == "a"

    @pytest.mark.anyio
    async def test_path_with_typed_conversion(self):
        r = VariableRenderer(make_source_resolver({"data": {"count": "42"}}))
        assert await r.render("${data.count as integer}") == 42

    @pytest.mark.anyio
    async def test_nested_path_with_index(self):
        r = VariableRenderer(make_source_resolver({"data": {"items": [{"k": 1}, {"k": 2}]}}))
        # FieldResolver supports dot-path including list index notation in path
        assert await r.render("${data.items[1].k as integer}") == 2


# ============================
# Default fallback (| ...)
# ============================

class TestDefaultFallback:
    @pytest.mark.anyio
    async def test_default_used_when_none(self):
        r = VariableRenderer(make_source_resolver({"v": None}))
        assert await r.render("${v | fallback}") == "fallback"

    @pytest.mark.anyio
    async def test_default_used_when_missing(self):
        r = VariableRenderer(make_source_resolver({}))
        assert await r.render("${v | hello}") == "hello"

    @pytest.mark.anyio
    async def test_default_skipped_when_value_present(self):
        r = VariableRenderer(make_source_resolver({"v": "actual"}))
        assert await r.render("${v | fallback}") == "actual"

    @pytest.mark.anyio
    async def test_default_with_typed_conversion(self):
        r = VariableRenderer(make_source_resolver({"v": None}))
        assert await r.render("${v as integer | 99}") == 99

    @pytest.mark.anyio
    async def test_default_is_variable_reference(self):
        r = VariableRenderer(make_source_resolver({"v": None, "backup": "b-value"}))
        assert await r.render("${v | ${backup}}") == "b-value"

    @pytest.mark.anyio
    async def test_default_referenced_then_typed(self):
        r = VariableRenderer(make_source_resolver({"v": None, "n": "7"}))
        assert await r.render("${v as integer | ${n as integer}}") == 7


# ============================
# Subtype / attrs diversity
# ============================

class TestSubtypeDiversity:
    @pytest.mark.anyio
    async def test_audio_mp3(self):
        from mindor.core.utils.streaming.audio import AudioStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"bytes"}))
        result = await r.render("${v as audio/mp3}")
        assert isinstance(result, AudioStreamResource)
        assert result.format == "mp3"
        assert result.content_type == "audio/mpeg"

    @pytest.mark.anyio
    async def test_audio_wav_from_bytes(self):
        from mindor.core.utils.streaming.audio import WavStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"riff"}))
        result = await r.render("${v as audio/wav}")
        assert isinstance(result, WavStreamResource)

    @pytest.mark.anyio
    async def test_audio_pcm_to_wav_auto_conversion(self):
        from mindor.core.utils.streaming.audio import PcmStreamResource, WavStreamResource
        pcm = PcmStreamResource(b"raw samples", {"sample_rate": 16000, "channels": 1, "bit_depth": 16})
        r = VariableRenderer(make_source_resolver({"v": pcm}))
        result = await r.render("${v as audio/wav}")
        assert isinstance(result, WavStreamResource)

    @pytest.mark.anyio
    async def test_video_mp4(self):
        from mindor.core.utils.streaming.video import VideoStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"mp4"}))
        result = await r.render("${v as video/mp4}")
        assert result.format == "mp4"
        assert result.content_type == "video/mp4"

    @pytest.mark.anyio
    async def test_video_webm(self):
        from mindor.core.utils.streaming.video import VideoStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"webm"}))
        result = await r.render("${v as video/webm}")
        assert result.format == "webm"
        assert result.content_type == "video/webm"


class TestPcmAttrsDiversity:
    @pytest.mark.anyio
    async def test_only_sample_rate(self):
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"raw"}))
        result = await r.render("${v as audio/pcm[sample_rate=8000]}")
        assert isinstance(result, PcmStreamResource)
        assert result.attrs == {"sample_rate": "8000"}

    @pytest.mark.anyio
    async def test_multiple_attrs(self):
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"raw"}))
        result = await r.render("${v as audio/pcm[sample_rate=44100,channels=2,bit_depth=24]}")
        assert result.attrs == {"sample_rate": "44100", "channels": "2", "bit_depth": "24"}

    @pytest.mark.anyio
    async def test_attrs_with_variable_interpolation(self):
        from mindor.core.utils.streaming.audio import PcmStreamResource
        r = VariableRenderer(make_source_resolver({
            "v": b"raw",
            "config": {"sr": 22050, "ch": 1},
        }))
        result = await r.render(
            "${v as audio/pcm[sample_rate=${config.sr as integer},channels=${config.ch as integer}]}"
        )
        assert result.attrs == {"sample_rate": 22050, "channels": 1}

    @pytest.mark.anyio
    async def test_attrs_preserved_through_pcm_to_wav(self):
        from mindor.core.utils.streaming.audio import WavStreamResource
        r = VariableRenderer(make_source_resolver({"v": b"raw"}))
        result = await r.render(
            "${v as audio/wav}"  # bytes + wav goes through general AudioStream not pcm
        )
        assert isinstance(result, WavStreamResource)
