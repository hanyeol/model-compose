"""
Stream multiplexing primitives for the IPC runtime.

The codec (`VariableCodec`) only emits/parses `__variable__` markers and delegates
stream registration to caller-provided callbacks. This module supplies:

- `IpcInboundStream` — consumer-side stream: holds `queue`, wire→value decode
  (`decode_chunk`), end/abort sentinels, and resource wrapping.
- `IpcOutboundStream` — producer-side stream: holds source/iterator/seq, value→
  wire encode (`encode_chunk`).
- `IpcStreamReader` — async-iterable proxy returned to the consumer; sends
  STREAM_PULL on each consume and STREAM_CLOSE on aclose().

Backpressure: credit = 1 (one-at-a-time pull).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Type, Union
from collections.abc import AsyncIterator
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, StreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.audio import PcmStreamResource, WavStreamResource, AudioStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
import asyncio, base64

# Sentinels placed in IpcInboundStream.queue.
_STREAM_END   = object()
_STREAM_ABORT = object()

class IpcInboundStream:
    """Consumer-side bookkeeping for one inbound stream.

    Held in `IpcRuntimeWorker._inbound_streams` (when worker receives input) or
    `IpcRuntimeProxy._inbound_streams` (when manager receives output). The
    `queue` carries decoded chunks (or sentinels) to the proxy iterator.
    """
    def __init__(self, stream_id: str, kind: StreamKind, codec: VariableCodec):
        self.stream_id: str = stream_id
        self.kind: StreamKind = kind
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.closed: bool = False

        self._codec: VariableCodec = codec

    def decode_chunk(self, data: Any) -> Any:
        """Convert on-wire chunk data back to the Python value for this stream's kind.

        - StreamKind.BYTES  ← base64 string → bytes
        - StreamKind.TEXT   ← raw string
        - StreamKind.OBJECT ← codec.decode(data) (may contain nested __variable__ markers)
        """
        if self.kind == StreamKind.BYTES:
            if not isinstance(data, str):
                raise TypeError(f"bytes-kind chunk wire data must be a string, got {type(data).__name__}")
            return base64.b64decode(data)

        if self.kind == StreamKind.TEXT:
            if not isinstance(data, str):
                raise TypeError(f"text-kind chunk wire data must be a string, got {type(data).__name__}")
            return data

        # StreamKind.OBJECT
        return self._codec.decode(data)

    def push_end(self) -> None:
        self.queue.put_nowait(_STREAM_END)

    def push_abort(self) -> None:
        self.queue.put_nowait(_STREAM_ABORT)

    def build_resource(
        self,
        reader: IpcStreamReader,
        content_type: Optional[str],
        filename: Optional[str],
        size: Optional[int],
        attrs: Dict[str, Any],
    ) -> Union[StreamResource, StreamChunkIterator]:
        """Wrap the `IpcStreamReader` in the appropriate `StreamResource` (or
        `StreamChunkIterator`) per §2.3.1 mapping. The returned object is what
        gets substituted into the decoded payload tree in place of the marker.

        For audio/video/wav/pcm: the reader is wrapped in
        `AsyncIterableStreamResource` and then passed as `source` to the domain
        resource.

        For image/text: the constructors require an in-memory object (PIL.Image /
        str), not a stream. We instead hand back an `AsyncIterableStreamResource`
        with the original content_type — the consuming component should decode
        via `load_image_from_stream(resource)` / equivalent.
        """
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

        # BytesStreamResource / ImageStreamResource / TextStreamResource → keep
        # the raw async-iterable resource; component decodes if it needs a
        # PIL.Image or decoded str.
        return source

    @staticmethod
    def _resolve_resource_class(content_type: Optional[str], kind: StreamKind) -> Type:
        """Return the `StreamResource` (or `StreamChunkIterator`) class to
        restore on the consumer side, based on the marker's `content_type`
        and `kind`.

        Falls back to `BytesStreamResource` (kind=bytes) or `StreamChunkIterator`
        (kind=text/object) when no MIME match is found.
        """
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

        # application/octet-stream or unspecified
        if kind == StreamKind.BYTES:
            return BytesStreamResource

        return StreamChunkIterator

class IpcOutboundStream:
    """Producer-side bookkeeping for one outbound stream.

    Held in `IpcRuntimeProxy._outbound_streams` (when manager produces input)
    or `IpcRuntimeWorker._outbound_streams` (when worker produces output).
    """
    def __init__(self, stream_id: str, kind: StreamKind, source: Any, codec: VariableCodec):
        self.stream_id: str = stream_id
        self.kind: StreamKind = kind
        self.source: Any = source
        self.seq: int = 0
        self.closed: bool = False

        self._codec: VariableCodec = codec
        self._iterator: AsyncIterator[Any] = source.__aiter__()

    async def next_chunk(self) -> Any:
        """Pull the next raw chunk from the source. Raises `StopAsyncIteration`
        when the source is exhausted."""
        return await self._iterator.__anext__()

    def encode_chunk(self, raw: Any) -> Any:
        """Convert a raw chunk yielded by the source into the on-wire form for
        `STREAM_CHUNK.payload.data`.

        - StreamKind.BYTES  → base64 string
        - StreamKind.TEXT   → raw string (str)
        - StreamKind.OBJECT → codec.encode(raw) (may contain nested __variable__ markers)
        """
        if self.kind == StreamKind.BYTES:
            if isinstance(raw, (bytes, bytearray)):
                return base64.b64encode(bytes(raw)).decode("ascii")
            raise TypeError(
                f"bytes-kind stream yielded non-bytes chunk: {type(raw).__name__}"
            )

        if self.kind == StreamKind.TEXT:
            if isinstance(raw, str):
                return raw
            raise TypeError(
                f"text-kind stream yielded non-str chunk: {type(raw).__name__}"
            )

        # StreamKind.OBJECT
        return self._codec.encode(raw)

class IpcStreamReader:
    """Async-iterable wrapped around an `IpcInboundStream`.

    Sends `STREAM_PULL` on each consume and `STREAM_CLOSE` on `aclose()`. The
    producer feeds chunks (or sentinels) into `stream.queue`; this proxy yields
    them until END/ABORT/CLOSE.
    """
    def __init__(
        self,
        stream: IpcInboundStream,
        on_pull: Callable[[str], Awaitable[None]],
        on_close: Callable[[str], Awaitable[None]],
    ):
        self._stream = stream
        self._on_pull = on_pull
        self._on_close = on_close
        self._started = False

    def __aiter__(self) -> "IpcStreamReader":
        return self

    async def __anext__(self) -> Any:
        if self._stream.closed:
            raise StopAsyncIteration

        # Credit=1: request next chunk before waiting.
        if not self._started:
            self._started = True
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
