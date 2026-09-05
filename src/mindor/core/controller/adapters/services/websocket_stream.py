"""
WebSocket stream multiplexing primitives.

Mirrors the IPC stream design (see mindor.core.foundation.runtime.ipc_stream)
but adapted for a WebSocket transport where:

- Text frames carry JSON control messages (stream_pull, stream_end, stream_abort,
  stream_close, and existing run_workflow/subscribe_task/etc.).
- Binary frames carry ONLY stream chunk payloads, using a slim prefix:

    [u16 BE stream_id_len][stream_id UTF-8][u32 BE seq][chunk bytes...]

Inbound streams (client -> server) are used for workflow input; outbound
streams (server -> client) for workflow output. Backpressure is credit=1:
the consumer sends a stream_pull for each chunk it wants; the producer
responds with one chunk frame.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Set, Tuple, Type, Union
from collections.abc import AsyncIterator, AsyncIterable
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, StreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.audio import PcmStreamResource, WavStreamResource, AudioStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
import asyncio, struct

# Binary chunk frame prefix: u16 stream_id length (bytes), then stream_id UTF-8,
# then u32 sequence, then the raw chunk payload.
_CHUNK_ID_LEN = struct.Struct(">H")
_CHUNK_SEQ = struct.Struct(">I")

# Sentinels placed in WebSocketInboundStream.queue.
_STREAM_END = object()
_STREAM_ABORT = object()

class WebSocketInboundStream:
    """Consumer-side bookkeeping for one inbound stream (client -> server).

    `queue` carries decoded chunks (or sentinels) to the reader. Backpressure
    is applied by the reader: it sends a stream_pull for each chunk it wants.
    """
    def __init__(self, stream_id: str, kind: StreamKind, codec: VariableCodec):
        self.stream_id: str = stream_id
        self.kind: StreamKind = kind
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.closed: bool = False

        self._codec: VariableCodec = codec

    def decode_chunk(self, data: Any) -> Any:
        if self.kind == StreamKind.BYTES:
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError(f"bytes-kind chunk wire data must be bytes, got {type(data).__name__}")
            return bytes(data)

        if self.kind == StreamKind.TEXT:
            if not isinstance(data, str):
                raise TypeError(f"text-kind chunk wire data must be a string, got {type(data).__name__}")
            return data

        return self._codec.decode(data)

    @staticmethod
    def decode_frame(data: bytes) -> Tuple[str, int, bytes]:
        """Unpack a binary WebSocket frame into (stream_id, seq, chunk)."""
        if len(data) < _CHUNK_ID_LEN.size:
            raise ValueError("chunk frame too short: missing stream_id length")

        (id_len,) = _CHUNK_ID_LEN.unpack_from(data, 0)
        header_end = _CHUNK_ID_LEN.size + id_len + _CHUNK_SEQ.size

        if len(data) < header_end:
            raise ValueError("chunk frame too short: incomplete header")

        stream_id = data[_CHUNK_ID_LEN.size:_CHUNK_ID_LEN.size + id_len].decode("utf-8")
        (seq,) = _CHUNK_SEQ.unpack_from(data, _CHUNK_ID_LEN.size + id_len)
        chunk = bytes(data[header_end:])

        return stream_id, seq, chunk

    def push_chunk(self, chunk: Any) -> None:
        self.queue.put_nowait(chunk)

    def push_end(self) -> None:
        self.queue.put_nowait(_STREAM_END)

    def push_abort(self) -> None:
        self.queue.put_nowait(_STREAM_ABORT)

    def build_resource(
        self,
        reader: "WebSocketStreamReader",
        content_type: Optional[str],
        filename: Optional[str],
        size: Optional[int],
        attrs: Dict[str, Any],
    ) -> Union[StreamResource, StreamChunkIterator]:
        cls = self._resolve_resource_class(content_type, self.kind)

        if cls is StreamChunkIterator:
            return StreamChunkIterator(reader)

        source = AsyncIterableStreamResource(
            reader,
            content_type=content_type,
            filename=filename,
            size=size,
        )

        if cls is PcmStreamResource:
            return PcmStreamResource(source, attrs=attrs, filename=filename)

        if cls is WavStreamResource:
            return WavStreamResource(source, attrs=attrs, filename=filename)

        if cls is AudioStreamResource:
            return AudioStreamResource(source, attrs=attrs, filename=filename)

        if cls is VideoStreamResource:
            return VideoStreamResource(source, attrs=attrs, filename=filename)

        return source

    @staticmethod
    def _resolve_resource_class(content_type: Optional[str], kind: StreamKind) -> Type:
        content_type = (content_type or "").lower()

        if content_type.startswith("image/"):
            return ImageStreamResource

        if content_type in ("audio/wav", "audio/x-wav"):
            return WavStreamResource

        if content_type in ("audio/l16", "audio/pcm"):
            return PcmStreamResource

        if content_type.startswith("audio/"):
            return AudioStreamResource

        if content_type.startswith("video/"):
            return VideoStreamResource

        if content_type.startswith("text/"):
            return TextStreamResource

        if kind == StreamKind.BYTES:
            return BytesStreamResource

        return StreamChunkIterator

class WebSocketOutboundStream:
    """Producer-side bookkeeping for one outbound stream (server -> client)."""
    def __init__(self, stream_id: str, kind: StreamKind, source: Any, codec: VariableCodec):
        self.stream_id: str = stream_id
        self.kind: StreamKind = kind
        self.source: Any = source
        self.seq: int = 0
        self.closed: bool = False

        self._codec: VariableCodec = codec
        self._iterator: AsyncIterator[Any] = source.__aiter__()

    async def next_chunk(self) -> Any:
        return await self._iterator.__anext__()

    def encode_chunk(self, payload: Any) -> Any:
        if self.kind == StreamKind.BYTES:
            if isinstance(payload, (bytes, bytearray)):
                return bytes(payload)

            raise TypeError(f"bytes-kind stream yielded non-bytes chunk: {type(payload).__name__}")

        if self.kind == StreamKind.TEXT:
            if isinstance(payload, str):
                return payload

            raise TypeError(f"text-kind stream yielded non-str chunk: {type(payload).__name__}")

        return self._codec.encode(payload)

    def encode_frame(self, chunk: bytes) -> bytes:
        """Pack a BYTES-kind chunk into a WebSocket binary frame payload.

        Uses this stream's `stream_id` and advances `self.seq` on each call.
        """
        stream_id_bytes = self.stream_id.encode("utf-8")

        if len(stream_id_bytes) > 0xFFFF:
            raise ValueError(f"stream_id too long: {len(stream_id_bytes)} bytes")

        payload = b"".join([
            _CHUNK_ID_LEN.pack(len(stream_id_bytes)),
            stream_id_bytes,
            _CHUNK_SEQ.pack(self.seq),
            chunk,
        ])
        self.seq += 1

        return payload

    async def aclose(self) -> None:
        aclose = getattr(self._iterator, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            except Exception:
                pass

class WebSocketStreamReader:
    """Async-iterable wrapped around a WebSocketInboundStream.

    Sends stream_pull on each consume and stream_close on aclose(). The
    producer feeds chunks (or sentinels) into stream.queue; this proxy yields
    them until END/ABORT/CLOSE.
    """
    def __init__(
        self,
        stream: WebSocketInboundStream,
        on_pull: Callable[[str], Awaitable[None]],
        on_close: Callable[[str], Awaitable[None]],
    ):
        self._stream = stream
        self._on_pull = on_pull
        self._on_close = on_close

    def __aiter__(self) -> "WebSocketStreamReader":
        return self

    async def __anext__(self) -> Any:
        if self._stream.closed:
            raise StopAsyncIteration

        await self._on_pull(self._stream.stream_id)
        item = await self._stream.queue.get()

        if item is _STREAM_END:
            self._stream.closed = True
            raise StopAsyncIteration
        if item is _STREAM_ABORT:
            self._stream.closed = True
            raise IOError(f"Stream {self._stream.stream_id} aborted")

        return item

    async def aclose(self) -> None:
        if self._stream.closed:
            return

        self._stream.closed = True

        try:
            await self._on_close(self._stream.stream_id)
        except Exception:
            pass

class WebSocketStreamRegistry:
    """Per-connection registry of inbound and outbound streams.

    Keyed by (client_id, stream_id). On connection close, all registered
    streams are aborted so any in-flight workflow observes the disconnect.
    """
    def __init__(self):
        self._inbound: Dict[Tuple[str, str], WebSocketInboundStream] = {}
        self._outbound: Dict[Tuple[str, str], WebSocketOutboundStream] = {}
        self._client_streams: Dict[str, Set[str]] = {}

    def register_inbound(self, client_id: str, stream: WebSocketInboundStream) -> None:
        self._inbound[(client_id, stream.stream_id)] = stream
        self._client_streams.setdefault(client_id, set()).add(stream.stream_id)

    def register_outbound(self, client_id: str, stream: WebSocketOutboundStream) -> None:
        self._outbound[(client_id, stream.stream_id)] = stream
        self._client_streams.setdefault(client_id, set()).add(stream.stream_id)

    def get_inbound(self, client_id: str, stream_id: str) -> Optional[WebSocketInboundStream]:
        return self._inbound.get((client_id, stream_id))

    def get_outbound(self, client_id: str, stream_id: str) -> Optional[WebSocketOutboundStream]:
        return self._outbound.get((client_id, stream_id))

    def remove_inbound(self, client_id: str, stream_id: str) -> Optional[WebSocketInboundStream]:
        stream = self._inbound.pop((client_id, stream_id), None)
        streams = self._client_streams.get(client_id)
        if streams is not None:
            streams.discard(stream_id)
        return stream

    def remove_outbound(self, client_id: str, stream_id: str) -> Optional[WebSocketOutboundStream]:
        stream = self._outbound.pop((client_id, stream_id), None)
        streams = self._client_streams.get(client_id)
        if streams is not None:
            streams.discard(stream_id)
        return stream

    async def close(self, client_id: str) -> None:
        stream_ids = self._client_streams.pop(client_id, set())

        for stream_id in stream_ids:
            inbound = self._inbound.pop((client_id, stream_id), None)

            if inbound is not None and not inbound.closed:
                inbound.push_abort()

            outbound = self._outbound.pop((client_id, stream_id), None)

            if outbound is not None and not outbound.closed:
                outbound.closed = True
                await outbound.aclose()
