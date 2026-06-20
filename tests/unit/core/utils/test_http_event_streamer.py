"""Tests for HttpEventStreamer encoding and SSE framing."""

import pytest
from mindor.core.utils.http_stream import HttpEventStreamer
from mindor.core.utils.streaming.stream import EventStreamFormat


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def make_iterator(chunks):
    for chunk in chunks:
        yield chunk


async def collect_stream(streamer: HttpEventStreamer) -> bytes:
    out = bytearray()
    async for piece in streamer.stream():
        out += piece
    return bytes(out)


class TestHttpEventStreamerTextFormat:
    @pytest.mark.anyio
    async def test_single_text_chunk(self):
        streamer = HttpEventStreamer(make_iterator(["hello"]), EventStreamFormat.TEXT)
        assert await collect_stream(streamer) == b"data: hello\n\n"

    @pytest.mark.anyio
    async def test_multiple_text_chunks(self):
        streamer = HttpEventStreamer(make_iterator(["hello", "world"]), EventStreamFormat.TEXT)
        assert await collect_stream(streamer) == b"data: hello\n\ndata: world\n\n"

    @pytest.mark.anyio
    async def test_multiline_text_chunk_split_to_data_lines(self):
        streamer = HttpEventStreamer(make_iterator(["line1\nline2"]), EventStreamFormat.TEXT)
        assert await collect_stream(streamer) == b"data: line1\ndata: line2\n\n"

    @pytest.mark.anyio
    async def test_non_string_chunk_stringified(self):
        streamer = HttpEventStreamer(make_iterator([42]), EventStreamFormat.TEXT)
        assert await collect_stream(streamer) == b"data: 42\n\n"


class TestHttpEventStreamerJsonFormat:
    @pytest.mark.anyio
    async def test_dict_chunk_serialized_as_json(self):
        streamer = HttpEventStreamer(make_iterator([{"key": "value"}]), EventStreamFormat.JSON)
        assert await collect_stream(streamer) == b'data: {"key": "value"}\n\n'

    @pytest.mark.anyio
    async def test_scalar_chunk_serialized_as_json(self):
        streamer = HttpEventStreamer(make_iterator([42]), EventStreamFormat.JSON)
        assert await collect_stream(streamer) == b"data: 42\n\n"

    @pytest.mark.anyio
    async def test_multiple_json_chunks(self):
        streamer = HttpEventStreamer(make_iterator([{"a": 1}, {"b": 2}]), EventStreamFormat.JSON)
        assert await collect_stream(streamer) == b'data: {"a": 1}\n\ndata: {"b": 2}\n\n'


class TestHttpEventStreamerNoneSkipping:
    @pytest.mark.anyio
    async def test_none_chunks_skipped(self):
        streamer = HttpEventStreamer(make_iterator(["hello", None, "world"]), EventStreamFormat.TEXT)
        assert await collect_stream(streamer) == b"data: hello\n\ndata: world\n\n"


class TestHttpEventStreamerNoFormat:
    @pytest.mark.anyio
    async def test_str_chunk_passes_through(self):
        streamer = HttpEventStreamer(make_iterator(["hello"]), None)
        assert await collect_stream(streamer) == b"data: hello\n\n"

    @pytest.mark.anyio
    async def test_dict_chunk_falls_back_to_json(self):
        streamer = HttpEventStreamer(make_iterator([{"k": "v"}]), None)
        assert await collect_stream(streamer) == b'data: {"k": "v"}\n\n'
