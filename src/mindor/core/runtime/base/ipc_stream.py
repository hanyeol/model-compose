"""
Stream multiplexing primitives for the IPC runtime.

The codec (`VariableCodec`) only emits/parses `__variable__` markers and delegates
stream registration to caller-provided callbacks. This module supplies:

- `OutboundStreamState` / `InboundStreamState` — per-stream bookkeeping held by
  manager / worker respectively (see component-ipc.md §8.2).
- `mime_to_resource_class()` — MIME ↔ StreamResource mapping (§2.3.1).
- `encode_chunk_data()` / `decode_chunk_data()` — chunk-wire <-> Python value
  conversion driven by the stream marker's `kind` (§3.2).
- `InboundStreamProxy` — async-iterable proxy returned to the consumer; sends
  STREAM_PULL on each consume and STREAM_CLOSE on aclose().

Backpressure: credit = 1 (one-at-a-time pull). See §4.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Type
from dataclasses import dataclass, field
from collections.abc import AsyncIterator, AsyncIterable
from mindor.core.foundation.streaming.resources import StreamResource, AsyncIterableStreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.audio import PcmStreamResource, WavStreamResource, AudioStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.variable.codec import StreamKind
import asyncio, base64

@dataclass
class OutboundStreamState:
    """Producer-side bookkeeping for one outbound stream.

    Held in `IpcRuntimeManager._outbound_streams` (when manager produces input)
    or `IpcRuntimeWorker._outbound_streams` (when worker produces output).
    """
    stream_id: str
    kind: StreamKind
    source: Any  # original StreamResource / AsyncIterator / StreamIterator
    iterator: AsyncIterator[Any]  # cached __aiter__ result
    seq: int = 0
    closed: bool = False

@dataclass
class InboundStreamState:
    """Consumer-side bookkeeping for one inbound stream.

    Held in `IpcRuntimeWorker._inbound_streams` (when worker receives input)
    or `IpcRuntimeManager._inbound_streams` (when manager receives output).
    The `queue` carries decoded chunks (or sentinels) to the proxy iterator.
    """
    stream_id: str
    kind: StreamKind
    queue: asyncio.Queue[Any]
    closed: bool = False

# Sentinels placed in InboundStreamState.queue.
_STREAM_END   = object()
_STREAM_ABORT = object()

# ---------------------------------------------------------------------------
# MIME ↔ StreamResource mapping (§2.3.1)
# ---------------------------------------------------------------------------

def mime_to_resource_class(content_type: Optional[str], kind: StreamKind) -> Type:
    """Return the `StreamResource` (or `StreamChunkIterator`) class to restore on
    the consumer side, based on the marker's `content_type` and `kind`.

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

# ---------------------------------------------------------------------------
# Chunk-wire encode/decode (§3.2)
# ---------------------------------------------------------------------------

def encode_chunk_data(
    raw: Any,
    kind: StreamKind,
    codec_encode: Optional[Callable[[Any], Any]] = None,
) -> Any:
    """Convert a raw chunk yielded by the source into the on-wire form for
    `STREAM_CHUNK.payload.data`.

    - StreamKind.BYTES  → base64 string
    - StreamKind.TEXT   → raw string (str)
    - StreamKind.OBJECT → codec.encode(raw) (may contain nested __variable__ markers)
    """
    if kind == StreamKind.BYTES:
        if isinstance(raw, (bytes, bytearray)):
            return base64.b64encode(bytes(raw)).decode("ascii")
        raise TypeError(
            f"bytes-kind stream yielded non-bytes chunk: {type(raw).__name__}"
        )

    if kind == StreamKind.TEXT:
        if isinstance(raw, str):
            return raw
        raise TypeError(
            f"text-kind stream yielded non-str chunk: {type(raw).__name__}"
        )

    # StreamKind.OBJECT
    if codec_encode is None:
        return raw
    return codec_encode(raw)


def decode_chunk_data(
    data: Any,
    kind: StreamKind,
    codec_decode: Optional[Callable[[Any], Any]] = None,
) -> Any:
    """Inverse of `encode_chunk_data`."""
    if kind == StreamKind.BYTES:
        if not isinstance(data, str):
            raise TypeError(
                f"bytes-kind chunk wire data must be a string, got {type(data).__name__}"
            )
        return base64.b64decode(data)

    if kind == StreamKind.TEXT:
        if not isinstance(data, str):
            raise TypeError(
                f"text-kind chunk wire data must be a string, got {type(data).__name__}"
            )
        return data

    # StreamKind.OBJECT
    if codec_decode is None:
        return data
    return codec_decode(data)


# ---------------------------------------------------------------------------
# Consumer-side proxy iterator
# ---------------------------------------------------------------------------

class InboundStreamProxy:
    """Async-iterable wrapped around an `InboundStreamState`.

    Sends `STREAM_PULL` on each consume and `STREAM_CLOSE` on `aclose()`. The
    producer feeds chunks (or sentinels) into `state.queue`; this proxy yields
    them until END/ABORT/CLOSE.
    """
    def __init__(
        self,
        state: InboundStreamState,
        on_pull: Callable[[str], Awaitable[None]],
        on_close: Callable[[str], Awaitable[None]],
    ):
        self._state = state
        self._on_pull = on_pull
        self._on_close = on_close
        self._started = False

    def __aiter__(self) -> "InboundStreamProxy":
        return self

    async def __anext__(self) -> Any:
        if self._state.closed:
            raise StopAsyncIteration

        # Credit=1: request next chunk before waiting.
        if not self._started:
            self._started = True
        await self._on_pull(self._state.stream_id)

        item = await self._state.queue.get()

        if item is _STREAM_END:
            self._state.closed = True
            raise StopAsyncIteration
        if item is _STREAM_ABORT:
            self._state.closed = True
            raise IOError(f"Stream {self._state.stream_id} aborted")

        return item

    async def aclose(self) -> None:
        if self._state.closed:
            return
        self._state.closed = True
        try:
            await self._on_close(self._state.stream_id)
        except Exception:
            pass


def push_stream_end(state: InboundStreamState) -> None:
    state.queue.put_nowait(_STREAM_END)


def push_stream_abort(state: InboundStreamState) -> None:
    state.queue.put_nowait(_STREAM_ABORT)

# ---------------------------------------------------------------------------
# Resource construction on the consumer side
# ---------------------------------------------------------------------------

def build_inbound_resource(
    state: InboundStreamState,
    proxy: InboundStreamProxy,
    content_type: Optional[str],
    filename: Optional[str],
    size: Optional[int],
    attrs: Dict[str, Any],
) -> Any:
    """Wrap the `InboundStreamProxy` in the appropriate `StreamResource` (or
    `StreamChunkIterator`) per §2.3.1 mapping. The returned object is what gets
    substituted into the decoded payload tree in place of the marker.

    For audio/video/wav/pcm: the proxy is wrapped in `AsyncIterableStreamResource`
    and then passed as `source` to the domain resource.

    For image/text: the constructors require an in-memory object (PIL.Image / str),
    not a stream. We instead hand back an `AsyncIterableStreamResource` with the
    original content_type — the consuming component should decode via
    `load_image_from_stream(resource)` / equivalent (see spec §6.3).
    """
    cls = mime_to_resource_class(content_type, state.kind)

    if cls is StreamChunkIterator:
        return StreamChunkIterator(proxy)

    source = AsyncIterableStreamResource(
        proxy,
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

    # BytesStreamResource / ImageStreamResource / TextStreamResource → keep the
    # raw async-iterable resource; component decodes if it needs a PIL.Image or
    # decoded str.
    return source
