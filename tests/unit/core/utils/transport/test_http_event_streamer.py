"""Tests for HttpEventStreamer SSE framing.

Chunk encoding (text/json serialization) is the responsibility of
``EventStreamIterator`` and is tested separately. This module focuses on
how already-encoded chunks are framed into SSE ``data:`` lines.
"""

import pytest
from mindor.core.utils.transport.http_stream import HttpEventStreamer


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


class TestHttpEventStreamerFraming:
    @pytest.mark.anyio
    async def test_single_str_chunk(self):
        streamer = HttpEventStreamer(make_iterator(["hello"]))
        assert await collect_stream(streamer) == b"data: hello\n\n"

    @pytest.mark.anyio
    async def test_multiple_chunks(self):
        streamer = HttpEventStreamer(make_iterator(["hello", "world"]))
        assert await collect_stream(streamer) == b"data: hello\n\ndata: world\n\n"

    @pytest.mark.anyio
    async def test_multiline_chunk_split_to_data_lines(self):
        streamer = HttpEventStreamer(make_iterator(["line1\nline2"]))
        assert await collect_stream(streamer) == b"data: line1\ndata: line2\n\n"

    @pytest.mark.anyio
    async def test_bytes_chunk(self):
        streamer = HttpEventStreamer(make_iterator([b"hello"]))
        assert await collect_stream(streamer) == b"data: hello\n\n"

    @pytest.mark.anyio
    async def test_none_chunks_skipped(self):
        streamer = HttpEventStreamer(make_iterator(["hello", None, "world"]))
        assert await collect_stream(streamer) == b"data: hello\n\ndata: world\n\n"
