"""Unit tests for `component/runtime/base/ipc_stream.py`.

Covers the streaming primitives that the integration tests don't reach:
- `IpcOutboundStream.encode_chunk` / `IpcInboundStream.decode_chunk` for
  BYTES, TEXT, OBJECT kinds.
- Wire-type validation: malformed chunk data raises `TypeError`.
- `IpcStreamReader` lifecycle: credit=1 PULL, END/ABORT/CLOSE handling.
- `_resolve_resource_class` mapping table.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from mindor.core.component.runtime.base.ipc_stream import (
    IpcInboundStream,
    IpcOutboundStream,
    IpcStreamReader,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.audio import (
    AudioStreamResource,
    PcmStreamResource,
    WavStreamResource,
)
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.codec import StreamKind


class _FakeCodec:
    """Minimal stand-in for `VariableCodec` used only for OBJECT-kind streams."""
    def encode(self, value):
        return {"wrapped": value}

    def decode(self, value):
        return {"decoded": value}


class _IdentityCodec:
    def encode(self, value):
        return value

    def decode(self, value):
        return value


class _EmptyAsyncIterable:
    """`IpcOutboundStream.__init__` calls `source.__aiter__()`, so a bare source
    must at least implement it. We never iterate in these unit tests."""
    def __aiter__(self):
        return self


def _outbound(kind: StreamKind, codec=None) -> IpcOutboundStream:
    return IpcOutboundStream(
        stream_id="s1",
        kind=kind,
        source=_EmptyAsyncIterable(),
        codec=codec or _IdentityCodec(),
    )


def _inbound(kind: StreamKind = StreamKind.BYTES, stream_id: str = "s1", codec=None) -> IpcInboundStream:
    return IpcInboundStream(stream_id=stream_id, kind=kind, codec=codec or _IdentityCodec())


# ---------------------------------------------------------------------------
# IpcOutboundStream.encode_chunk
# ---------------------------------------------------------------------------

class TestEncodeChunk:
    def test_bytes_kind_passes_bytes_through(self):
        out = _outbound(StreamKind.BYTES)
        inb = _inbound(StreamKind.BYTES)
        wire = out.encode_chunk(b"hello\x00\xff")
        # BYTES chunks are handed off to the wire layer as raw bytes; the
        # transport places them in the IpcMessage binary trailer.
        assert wire == b"hello\x00\xff"
        assert inb.decode_chunk(wire) == b"hello\x00\xff"

    def test_bytes_kind_accepts_bytearray(self):
        out = _outbound(StreamKind.BYTES)
        inb = _inbound(StreamKind.BYTES)
        wire = out.encode_chunk(bytearray(b"abc"))
        assert wire == b"abc"
        assert isinstance(wire, bytes)
        assert inb.decode_chunk(wire) == b"abc"

    def test_bytes_kind_rejects_non_bytes(self):
        out = _outbound(StreamKind.BYTES)
        with pytest.raises(TypeError, match="bytes-kind"):
            out.encode_chunk("not bytes")

    def test_text_kind_passes_str_through(self):
        out = _outbound(StreamKind.TEXT)
        inb = _inbound(StreamKind.TEXT)
        wire = out.encode_chunk("héllo 🌊")
        assert wire == "héllo 🌊"
        assert inb.decode_chunk(wire) == "héllo 🌊"

    def test_text_kind_rejects_non_str(self):
        out = _outbound(StreamKind.TEXT)
        with pytest.raises(TypeError, match="text-kind"):
            out.encode_chunk(b"bytes here")

    def test_object_kind_uses_codec_encode(self):
        out = _outbound(StreamKind.OBJECT, codec=_FakeCodec())
        wire = out.encode_chunk({"x": 1})
        assert wire == {"wrapped": {"x": 1}}


# ---------------------------------------------------------------------------
# IpcInboundStream.decode_chunk
# ---------------------------------------------------------------------------

class TestDecodeChunk:
    def test_bytes_kind_requires_bytes_wire(self):
        inb = _inbound(StreamKind.BYTES)
        with pytest.raises(TypeError, match="bytes-kind chunk wire data"):
            inb.decode_chunk("not bytes")

    def test_bytes_kind_requires_bytes_wire_for_dicts_too(self):
        inb = _inbound(StreamKind.BYTES)
        with pytest.raises(TypeError, match="bytes-kind chunk wire data"):
            inb.decode_chunk({"oops": True})

    def test_text_kind_requires_string_wire(self):
        inb = _inbound(StreamKind.TEXT)
        with pytest.raises(TypeError, match="text-kind chunk wire data"):
            inb.decode_chunk(b"raw bytes")

    def test_object_kind_uses_codec_decode(self):
        inb = _inbound(StreamKind.OBJECT, codec=_FakeCodec())
        result = inb.decode_chunk({"x": 1})
        assert result == {"decoded": {"x": 1}}


# ---------------------------------------------------------------------------
# IpcStreamReader
# ---------------------------------------------------------------------------

class _PullCloseRecorder:
    """Captures `on_pull` / `on_close` calls for assertions."""
    def __init__(self):
        self.pulls: List[str] = []
        self.closes: List[str] = []

    async def on_pull(self, stream_id: str) -> None:
        self.pulls.append(stream_id)

    async def on_close(self, stream_id: str) -> None:
        self.closes.append(stream_id)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestIpcStreamReader:
    @pytest.mark.anyio
    async def test_consumes_chunks_until_end(self):
        stream = _inbound()
        rec = _PullCloseRecorder()
        reader = IpcStreamReader(stream, on_pull=rec.on_pull, on_close=rec.on_close)

        # Producer enqueues two chunks then END.
        stream.queue.put_nowait(b"chunk-1")
        stream.queue.put_nowait(b"chunk-2")
        stream.push_end()

        received = [item async for item in reader]
        assert received == [b"chunk-1", b"chunk-2"]
        # Credit=1: one PULL per __anext__, including the one that drained END.
        assert rec.pulls == [stream.stream_id, stream.stream_id, stream.stream_id]
        # END must close the stream and not trigger a CLOSE message.
        assert stream.closed is True
        assert rec.closes == []

    @pytest.mark.anyio
    async def test_abort_raises_ioerror_and_closes(self):
        stream = _inbound(stream_id="aborted-stream")
        rec = _PullCloseRecorder()
        reader = IpcStreamReader(stream, on_pull=rec.on_pull, on_close=rec.on_close)

        stream.queue.put_nowait(b"first")
        stream.push_abort()

        it = reader.__aiter__()
        assert await it.__anext__() == b"first"

        with pytest.raises(IOError, match="aborted-stream"):
            await it.__anext__()
        assert stream.closed is True
        # ABORT is producer-initiated; consumer aclose() should be a no-op.
        await reader.aclose()
        assert rec.closes == []

    @pytest.mark.anyio
    async def test_aclose_sends_stream_close_and_marks_closed(self):
        stream = _inbound(stream_id="closing-stream")
        rec = _PullCloseRecorder()
        reader = IpcStreamReader(stream, on_pull=rec.on_pull, on_close=rec.on_close)

        await reader.aclose()
        assert stream.closed is True
        assert rec.closes == ["closing-stream"]

        # Subsequent iteration raises immediately without another PULL.
        with pytest.raises(StopAsyncIteration):
            await reader.__anext__()
        assert rec.pulls == []

    @pytest.mark.anyio
    async def test_aclose_is_idempotent(self):
        stream = _inbound()
        rec = _PullCloseRecorder()
        reader = IpcStreamReader(stream, on_pull=rec.on_pull, on_close=rec.on_close)

        await reader.aclose()
        await reader.aclose()
        # Second aclose() must NOT emit another STREAM_CLOSE.
        assert rec.closes == [stream.stream_id]

    @pytest.mark.anyio
    async def test_aclose_swallows_send_failure(self):
        stream = _inbound()

        async def failing_pull(stream_id: str) -> None:
            return None

        async def failing_close(stream_id: str) -> None:
            raise RuntimeError("transport broken")

        reader = IpcStreamReader(stream, on_pull=failing_pull, on_close=failing_close)

        # The contract says aclose() must not propagate transport errors —
        # the consumer is shutting down anyway.
        await reader.aclose()
        assert stream.closed is True


# ---------------------------------------------------------------------------
# IpcInboundStream._resolve_resource_class
# ---------------------------------------------------------------------------

class TestMimeToResourceClass:
    @pytest.mark.parametrize(
        ("content_type", "expected"),
        [
            ("image/png", ImageStreamResource),
            ("image/jpeg", ImageStreamResource),
            ("audio/wav", WavStreamResource),
            ("audio/x-wav", WavStreamResource),
            ("audio/l16", PcmStreamResource),
            ("audio/pcm", PcmStreamResource),
            ("audio/mpeg", AudioStreamResource),
            ("video/mp4", VideoStreamResource),
            ("text/plain", TextStreamResource),
            # MIME matching is case-insensitive (the implementation lowercases).
            ("IMAGE/PNG", ImageStreamResource),
        ],
    )
    def test_mime_specific_mapping(self, content_type, expected):
        assert IpcInboundStream._resolve_resource_class(content_type, StreamKind.BYTES) is expected

    def test_unspecified_bytes_falls_back_to_bytes_resource(self):
        assert IpcInboundStream._resolve_resource_class(None, StreamKind.BYTES) is BytesStreamResource
        assert IpcInboundStream._resolve_resource_class("application/octet-stream", StreamKind.BYTES) is BytesStreamResource
        assert IpcInboundStream._resolve_resource_class("", StreamKind.BYTES) is BytesStreamResource

    def test_unspecified_text_falls_back_to_chunk_iterator(self):
        assert IpcInboundStream._resolve_resource_class(None, StreamKind.TEXT) is StreamChunkIterator

    def test_unspecified_object_falls_back_to_chunk_iterator(self):
        assert IpcInboundStream._resolve_resource_class(None, StreamKind.OBJECT) is StreamChunkIterator
