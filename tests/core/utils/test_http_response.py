import pytest
import json
from mindor.core.utils.http_response import HttpEventStreamer
from mindor.core.utils.streaming import EventIteratorStreamResource, StreamFormat


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

def make_iterator(chunks):
    """Create an EventIteratorStreamResource from a list of chunks."""
    async def _gen():
        for c in chunks:
            yield c
    return _gen()


def make_resource(chunks, format=None):
    """Create an EventIteratorStreamResource with given chunks and format."""
    return EventIteratorStreamResource(make_iterator(chunks), format)


def make_streamer(chunks, format=None):
    """Create an HttpEventStreamer from a list of chunks with given format."""
    return HttpEventStreamer(make_resource(chunks, format), format)


async def collect_stream(streamer):
    """Collect all bytes from a streamer into a list."""
    return [chunk async for chunk in streamer.stream()]


# ============================
# _encode_chunk
# ============================

class TestEncodeChunkText:
    def test_string_passthrough(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk("hello", StreamFormat.TEXT) == "hello"

    def test_int_to_str(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk(42, StreamFormat.TEXT) == "42"

    def test_dict_to_str(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk({"key": "value"}, StreamFormat.TEXT)
        assert isinstance(result, str)
        assert "key" in result

    def test_none_to_str(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk(None, StreamFormat.TEXT) == "None"

    def test_bytes_to_str(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk(b"binary", StreamFormat.TEXT)
        assert isinstance(result, str)

    def test_float_to_str(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk(3.14, StreamFormat.TEXT) == "3.14"

    def test_bool_to_str(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk(True, StreamFormat.TEXT) == "True"


class TestEncodeChunkJson:
    def test_dict_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk({"key": "value"}, StreamFormat.JSON)
        assert json.loads(result) == {"key": "value"}

    def test_string_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk("hello", StreamFormat.JSON)
        assert json.loads(result) == "hello"

    def test_int_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk(42, StreamFormat.JSON)
        assert json.loads(result) == 42

    def test_none_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk(None, StreamFormat.JSON)
        assert json.loads(result) is None

    def test_list_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk([1, 2, 3], StreamFormat.JSON)
        assert json.loads(result) == [1, 2, 3]

    def test_unicode_preserved(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk({"msg": "한글"}, StreamFormat.JSON)
        assert "한글" in result

    def test_json_produces_single_line(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk({"a": 1, "b": [2, 3]}, StreamFormat.JSON)
        assert "\n" not in result


class TestEncodeChunkNoFormat:
    def test_string_passthrough(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk("hello", None) == "hello"

    def test_bytes_passthrough(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk(b"binary", None) == b"binary"

    def test_none_returns_none(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        assert streamer._encode_chunk(None, None) is None

    def test_dict_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk({"key": "value"}, None)
        assert json.loads(result) == {"key": "value"}

    def test_int_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk(42, None)
        assert json.loads(result) == 42

    def test_list_to_json(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._encode_chunk([1, 2], None)
        assert json.loads(result) == [1, 2]


# ============================
# _split_chunk
# ============================

class TestSplitChunk:
    def test_bytes_as_single_element(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk(b"hello")
        assert result == [b"hello"]

    def test_plain_string(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("hello")
        assert result == [b"hello"]

    def test_multiline_string(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("line1\nline2\nline3")
        assert result == [b"line1", b"line2", b"line3"]

    def test_string_with_leading_newline(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("\nhello")
        assert result == [b"hello"]

    def test_string_with_trailing_newline(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("hello\n")
        assert result == [b"hello"]

    def test_string_with_both_newlines(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("\nhello\nworld\n")
        assert result == [b"hello", b"world"]

    def test_unicode_string(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("한글 테스트")
        assert result == ["한글 테스트".encode("utf-8")]

    def test_empty_string(self):
        streamer = HttpEventStreamer(make_resource([]), None)
        result = streamer._split_chunk("")
        assert result == [b""]


# ============================
# stream (end-to-end)
# ============================

class TestStreamEndToEnd:
    @pytest.mark.anyio
    async def test_single_text_chunk(self):
        resource = make_resource(["hello"], StreamFormat.TEXT)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [b"data: hello\n", b"\n"]

    @pytest.mark.anyio
    async def test_multiple_text_chunks(self):
        resource = make_resource(["hello", "world"], StreamFormat.TEXT)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [
            b"data: hello\n", b"\n",
            b"data: world\n", b"\n",
        ]

    @pytest.mark.anyio
    async def test_json_dict_chunk(self):
        resource = make_resource([{"key": "value"}], StreamFormat.JSON)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert len(output) == 2
        assert output[0].startswith(b"data: ")
        assert output[1] == b"\n"
        data = json.loads(output[0][6:-1])
        assert data == {"key": "value"}

    @pytest.mark.anyio
    async def test_none_format_skips_none_chunks(self):
        resource = make_resource(["hello", None, "world"], None)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [
            b"data: hello\n", b"\n",
            b"data: world\n", b"\n",
        ]

    @pytest.mark.anyio
    async def test_text_format_encodes_none_as_string(self):
        resource = make_resource([None], StreamFormat.TEXT)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [b"data: None\n", b"\n"]

    @pytest.mark.anyio
    async def test_json_format_encodes_none_as_null(self):
        resource = make_resource([None], StreamFormat.JSON)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [b"data: null\n", b"\n"]

    @pytest.mark.anyio
    async def test_multiline_text_splits_into_data_lines(self):
        resource = make_resource(["line1\nline2"], StreamFormat.TEXT)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [
            b"data: line1\n",
            b"data: line2\n",
            b"\n",
        ]

    @pytest.mark.anyio
    async def test_empty_stream(self):
        resource = make_resource([], StreamFormat.TEXT)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == []

    @pytest.mark.anyio
    async def test_bytes_chunk_no_format(self):
        resource = make_resource([b"raw bytes"], None)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [b"data: raw bytes\n", b"\n"]

    @pytest.mark.anyio
    async def test_int_chunk_text_format(self):
        resource = make_resource([42], StreamFormat.TEXT)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [b"data: 42\n", b"\n"]

    @pytest.mark.anyio
    async def test_int_chunk_json_format(self):
        resource = make_resource([42], StreamFormat.JSON)
        streamer = HttpEventStreamer(resource, resource.format)
        output = await collect_stream(streamer)
        assert output == [b"data: 42\n", b"\n"]
