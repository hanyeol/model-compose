from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
from typing import Dict, Optional, Type, Union, Any
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, StreamResource
from mindor.core.foundation.streaming.audio import AudioStreamResource, PcmStreamResource, WavStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from .codec import RedisStreamMeta
from .errors import StreamAbortError, StreamKindMismatchError
import base64
import json
import ulid

if TYPE_CHECKING:
    from redis.asyncio import Redis

_BLOB_KEY_PREFIX = "blob-key:"

class RedisOutboundStream:
    """Producer side: pushes chunks into a Redis stream via XADD.

    One instance is bound to a single `stream_key`. The caller may call
    `push_chunk` / `push_end` / `push_abort` in any order but must terminate
    exactly once with either `push_end` or `push_abort`.
    """
    def __init__(
        self,
        client: "Redis",
        meta: RedisStreamMeta,
        codec: VariableCodec,
        inline_bytes_threshold: int,
        blob_ttl: int,
        max_stream_length: Optional[int] = None,
    ):
        self.client = client
        self.meta = meta
        self._codec = codec
        self._inline_bytes_threshold = inline_bytes_threshold
        self._blob_ttl = blob_ttl
        self._max_stream_length = max_stream_length
        self._seq = 0

    async def push_chunk(self, chunk: Any) -> None:
        encoded = await self._encode_chunk(chunk)
        self._seq += 1
        fields = {
            "event": "chunk",
            "kind": self.meta.kind.value if isinstance(self.meta.kind, StreamKind) else self.meta.kind,
            "data": encoded,
            "seq": str(self._seq),
        }
        await self._xadd(fields)

    async def push_end(self) -> None:
        await self._xadd({"event": "end"})

    async def push_abort(self, error: str) -> None:
        await self._xadd({"event": "abort", "error": error})

    async def _xadd(self, fields: Dict[str, Any]) -> None:
        kwargs: Dict[str, Any] = {}
        if self._max_stream_length is not None:
            kwargs["maxlen"] = self._max_stream_length
            kwargs["approximate"] = True
        await self.client.xadd(self.meta.stream_key, fields, **kwargs)

    async def _encode_chunk(self, chunk: Any) -> str:
        kind = self.meta.kind
        if kind == StreamKind.BYTES:
            if not isinstance(chunk, (bytes, bytearray)):
                raise StreamKindMismatchError(
                    f"bytes-kind stream yielded non-bytes chunk: {type(chunk).__name__}"
                )
            raw = bytes(chunk)
            if len(raw) > self._inline_bytes_threshold:
                blob_key = f"{self.meta.stream_key}:chunk:{ulid.ulid()}"
                await self.client.setex(blob_key, self._blob_ttl, raw)
                return f"{_BLOB_KEY_PREFIX}{blob_key}"
            return base64.b64encode(raw).decode("ascii")

        if kind == StreamKind.TEXT:
            if not isinstance(chunk, str):
                raise StreamKindMismatchError(
                    f"text-kind stream yielded non-str chunk: {type(chunk).__name__}"
                )
            return chunk

        # StreamKind.OBJECT
        encoded = self._codec.encode(chunk)
        return json.dumps(encoded, ensure_ascii=False, default=str)

class RedisInboundStream:
    """Consumer side: async-iterates chunks from a Redis stream via XREAD."""
    def __init__(
        self,
        client: "Redis",
        meta: RedisStreamMeta,
        codec: VariableCodec,
        block_ms: int = 5000,
    ):
        self.client = client
        self.meta = meta
        self._codec = codec
        self._block_ms = block_ms
        self._last_id = "0-0"
        self._closed = False

    def __aiter__(self) -> "RedisInboundStream":
        return self

    async def __anext__(self) -> Any:
        if self._closed:
            raise StopAsyncIteration

        while True:
            responses = await self.client.xread(
                {self.meta.stream_key: self._last_id},
                count=1,
                block=self._block_ms,
            )

            if not responses:
                continue

            # XREAD returns [(stream_key, [(entry_id, fields), ...]), ...].
            # We queried a single stream with count=1, so exactly one entry.
            _, streams = responses[0]
            entry_id, fields = streams[0]

            self._last_id = self._decode_field(entry_id)
            event = self._decode_field(self._fields_get(fields, "event"))

            if event == "chunk":
                return await self._decode_chunk(fields)

            if event == "end":
                self._closed = True
                raise StopAsyncIteration

            if event == "abort":
                self._closed = True
                error = self._decode_field(self._fields_get(fields, "error")) or "stream aborted"
                raise StreamAbortError(error)
            # Unknown event — ignore and keep reading.

    async def aclose(self) -> None:
        self._closed = True

    def build_resource(self) -> Union[StreamResource, StreamChunkIterator]:
        cls = self._resolve_resource_class(self.meta.content_type, self.meta.kind)

        if cls is StreamChunkIterator:
            return StreamChunkIterator(self)

        source = AsyncIterableStreamResource(
            self,
            content_type=self.meta.content_type,
            filename=self.meta.filename,
            size=self.meta.size,
        )
        attrs = self.meta.attrs or {}

        if cls is PcmStreamResource:
            return PcmStreamResource(source, attrs=attrs, filename=self.meta.filename)

        if cls is WavStreamResource:
            return WavStreamResource(source, attrs=attrs, filename=self.meta.filename)

        if cls is AudioStreamResource:
            return AudioStreamResource(source, attrs=attrs, filename=self.meta.filename)

        if cls is VideoStreamResource:
            return VideoStreamResource(source, attrs=attrs, filename=self.meta.filename)

        # BytesStreamResource / ImageStreamResource / TextStreamResource → keep
        # the raw async-iterable resource; consumer decodes if it needs a
        # PIL.Image or decoded str.
        return source

    async def _decode_chunk(self, fields: Dict[Any, Any]) -> Any:
        kind_field = self._decode_field(self._fields_get(fields, "kind"))
        kind = StreamKind(kind_field) if kind_field else self.meta.kind
        raw = self._fields_get(fields, "data")
        data = self._decode_field(raw)

        if kind == StreamKind.BYTES:
            if isinstance(data, str) and data.startswith(_BLOB_KEY_PREFIX):
                blob_key = data[len(_BLOB_KEY_PREFIX):]
                payload = await self._consume_blob(blob_key)
                if payload is None:
                    raise StreamAbortError(f"stream blob missing: {blob_key}")
                return payload

            if isinstance(data, str):
                return base64.b64decode(data)

            if isinstance(data, (bytes, bytearray)):
                return bytes(data)

            raise StreamKindMismatchError(f"bytes-kind chunk data must be str/bytes, got {type(data).__name__}")

        if kind == StreamKind.TEXT:
            if not isinstance(data, str):
                raise StreamKindMismatchError(f"text-kind chunk data must be a string, got {type(data).__name__}")

            return data

        # StreamKind.OBJECT
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data).decode("utf-8")

        return self._codec.decode(json.loads(data))

    async def _consume_blob(self, key: str) -> Optional[bytes]:
        try:
            return await self.client.execute_command("GETDEL", key)
        except Exception as e:
            from redis.exceptions import ResponseError
            if not isinstance(e, ResponseError):
                raise

        async with self.client.pipeline(transaction=True) as pipeline:
            pipeline.get(key)
            pipeline.delete(key)
            data, _ = await pipeline.execute()

        return data

    @staticmethod
    def _decode_field(value: Any) -> Any:
        """XREAD returns bytes for keys/values; decode-once helper for our schema."""
        if isinstance(value, bytes):
            return value.decode("utf-8")

        return value

    @staticmethod
    def _fields_get(fields: Dict[Any, Any], name: str) -> Any:
        """Fetch a field value tolerating both bytes and str keys."""
        if name in fields:
            return fields[name]

        bytes_key = name.encode("utf-8")

        if bytes_key in fields:
            return fields[bytes_key]

        return None

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
