"""Tests for WebSocket stream multiplexing primitives."""

from typing import List
from unittest.mock import AsyncMock

import pytest

from mindor.core.controller.adapters.services.websocket_stream import (
    WebSocketInboundStream,
    WebSocketOutboundStream,
    WebSocketStreamReader,
    WebSocketStreamRegistry,
)
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _outbound(stream_id: str = "s1"):
    async def source():
        if False:
            yield

    return WebSocketOutboundStream(stream_id, StreamKind.BYTES, source(), VariableCodec())


class TestChunkFrameCodec:
    def test_round_trip(self):
        outbound = _outbound("s1")
        outbound.seq = 42
        payload = outbound.encode_frame(b"hello world")

        stream_id, seq, chunk = WebSocketInboundStream.decode_frame(payload)
        assert stream_id == "s1"
        assert seq == 42
        assert chunk == b"hello world"

    def test_multibyte_stream_id(self):
        outbound = _outbound("스트림-01")
        outbound.seq = 7
        payload = outbound.encode_frame(b"\x00\x01\x02")

        stream_id, seq, chunk = WebSocketInboundStream.decode_frame(payload)
        assert stream_id == "스트림-01"
        assert seq == 7
        assert chunk == b"\x00\x01\x02"

    def test_empty_chunk(self):
        outbound = _outbound("s1")
        payload = outbound.encode_frame(b"")

        stream_id, seq, chunk = WebSocketInboundStream.decode_frame(payload)
        assert stream_id == "s1"
        assert seq == 0
        assert chunk == b""

    def test_encode_frame_advances_seq(self):
        outbound = _outbound("s1")
        assert outbound.seq == 0
        outbound.encode_frame(b"a")
        assert outbound.seq == 1
        outbound.encode_frame(b"b")
        assert outbound.seq == 2

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            WebSocketInboundStream.decode_frame(b"\x00")

    def test_incomplete_header_raises(self):
        # length prefix says 100 bytes of stream_id but only 5 provided
        with pytest.raises(ValueError):
            WebSocketInboundStream.decode_frame(b"\x00\x64abcde")


class TestInboundStreamBuildResource:
    def test_video_content_type_wraps_video_resource(self):
        stream = WebSocketInboundStream("s1", StreamKind.BYTES, VariableCodec())
        reader = WebSocketStreamReader(stream, on_pull=AsyncMock(), on_close=AsyncMock())
        resource = stream.build_resource(reader, "video/mp4", "clip.mp4", None, {})
        assert isinstance(resource, VideoStreamResource)


class TestInboundStreamFlow:
    @pytest.mark.anyio
    async def test_pull_then_chunk_then_end(self):
        stream = WebSocketInboundStream("s1", StreamKind.BYTES, VariableCodec())
        pulled: List[str] = []
        closed: List[str] = []

        async def on_pull(sid: str) -> None:
            pulled.append(sid)

        async def on_close(sid: str) -> None:
            closed.append(sid)

        reader = WebSocketStreamReader(stream, on_pull=on_pull, on_close=on_close)

        stream.push_chunk(b"first")
        stream.push_chunk(b"second")
        stream.push_end()

        collected: List[bytes] = []
        async for chunk in reader:
            collected.append(chunk)

        assert collected == [b"first", b"second"]
        assert pulled == ["s1", "s1", "s1"]  # one pull per iteration including the final END
        assert closed == []  # END terminates naturally, no explicit close needed

    @pytest.mark.anyio
    async def test_abort_raises_ioerror(self):
        stream = WebSocketInboundStream("s1", StreamKind.BYTES, VariableCodec())
        reader = WebSocketStreamReader(stream, on_pull=AsyncMock(), on_close=AsyncMock())

        stream.push_chunk(b"partial")
        stream.push_abort()

        collected: List[bytes] = []
        with pytest.raises(IOError):
            async for chunk in reader:
                collected.append(chunk)

        assert collected == [b"partial"]

    @pytest.mark.anyio
    async def test_aclose_calls_on_close(self):
        stream = WebSocketInboundStream("s1", StreamKind.BYTES, VariableCodec())
        on_close = AsyncMock()
        reader = WebSocketStreamReader(stream, on_pull=AsyncMock(), on_close=on_close)

        await reader.aclose()
        on_close.assert_awaited_once_with("s1")


class TestOutboundStream:
    @pytest.mark.anyio
    async def test_iterates_bytes_source(self):
        async def source():
            yield b"a"
            yield b"b"

        outbound = WebSocketOutboundStream("s1", StreamKind.BYTES, source(), VariableCodec())
        assert outbound.encode_chunk(await outbound.next_chunk()) == b"a"
        assert outbound.encode_chunk(await outbound.next_chunk()) == b"b"
        with pytest.raises(StopAsyncIteration):
            await outbound.next_chunk()

    def test_bytes_kind_rejects_non_bytes(self):
        async def source():
            if False:
                yield

        outbound = WebSocketOutboundStream("s1", StreamKind.BYTES, source(), VariableCodec())
        with pytest.raises(TypeError):
            outbound.encode_chunk("not bytes")


class TestStreamRegistry:
    @pytest.mark.anyio
    async def test_close_aborts_inbound_streams(self):
        registry = WebSocketStreamRegistry()
        s1 = WebSocketInboundStream("s1", StreamKind.BYTES, VariableCodec())
        s2 = WebSocketInboundStream("s2", StreamKind.BYTES, VariableCodec())
        registry.register_inbound("client-a", s1)
        registry.register_inbound("client-a", s2)

        await registry.close("client-a")

        # Sentinels queued -> reading yields the abort sentinel
        assert not s1.queue.empty()
        assert not s2.queue.empty()

    def test_get_returns_none_for_unknown(self):
        registry = WebSocketStreamRegistry()
        assert registry.get_inbound("client-a", "s1") is None
        assert registry.get_outbound("client-a", "s1") is None

    def test_remove_is_idempotent(self):
        registry = WebSocketStreamRegistry()
        s1 = WebSocketInboundStream("s1", StreamKind.BYTES, VariableCodec())
        registry.register_inbound("client-a", s1)
        assert registry.remove_inbound("client-a", "s1") is s1
        assert registry.remove_inbound("client-a", "s1") is None
