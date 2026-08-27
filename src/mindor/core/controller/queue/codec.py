from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.logger import logging
from .errors import (
    BlobCorruptedError,
    BlobNotFoundError,
    BlobTooLargeError,
    BlobUnauthorizedError,
)
import ulid

if TYPE_CHECKING:
    from redis.asyncio import Redis

@dataclass
class RedisStreamMeta:
    """Descriptor for one stream flowing over Redis streams (XADD/XREAD).

    Populated when `QueueCodec.encode_*` sees a stream marker; the caller uses
    the returned mapping to spawn `RedisOutboundStream` producers. Also
    reconstructed on the decoding side from the `streams` section of the queue
    message so the reader can wrap chunks in the correct `StreamResource`.
    """
    stream_id: str
    kind: StreamKind
    content_type: Optional[str]
    filename: Optional[str]
    size: Optional[int]
    attrs: Optional[Dict[str, Any]]
    stream_key: str
    source: Any = None  # local-only handle to the producer source; not serialized

    def serialize(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value if isinstance(self.kind, StreamKind) else self.kind,
            "content_type": self.content_type,
            "filename": self.filename,
            "size": self.size,
            "attrs": self.attrs,
            "stream_key": self.stream_key,
        }

    @classmethod
    def deserialize(cls, stream_id: str, payload: Dict[str, Any]) -> "RedisStreamMeta":
        return cls(
            stream_id=stream_id,
            kind=StreamKind(payload["kind"]) if not isinstance(payload["kind"], StreamKind) else payload["kind"],
            content_type=payload.get("content_type"),
            filename=payload.get("filename"),
            size=payload.get("size"),
            attrs=payload.get("attrs"),
            stream_key=payload["stream_key"],
        )

StreamFactory = Callable[[RedisStreamMeta], Any]

class QueueCodec:
    """Redis-backed transport wrapper around `VariableCodec`.

    One instance is bound to a single `(task_id, run_id)` scope through the
    supplied `blob_prefix` / `stream_prefix`, so blob and stream keys emitted
    during encoding are automatically namespaced.
    """
    def __init__(
        self,
        client: "Redis",
        blob_prefix: str,
        stream_prefix: str,
        blob_ttl: int,
        result_ttl: int,
        inline_bytes_threshold: int,
        max_blob_size: Optional[int],
        stream_factory: Optional[StreamFactory] = None,
    ):
        self.client = client
        self.blob_prefix = blob_prefix
        self.stream_prefix = stream_prefix
        self.blob_ttl = blob_ttl
        self.result_ttl = result_ttl
        self.inline_bytes_threshold = inline_bytes_threshold
        self.max_blob_size = max_blob_size
        self._stream_factory = stream_factory
        self._codec = VariableCodec()

    async def encode_input(
        self, value: Any
    ) -> Tuple[Any, List[str], Dict[str, Dict[str, Any]]]:
        return await self._encode(value)

    async def encode_output(
        self, value: Any
    ) -> Tuple[Any, List[str], Dict[str, Dict[str, Any]]]:
        return await self._encode(value)

    async def decode_input(
        self, value: Any, streams: Dict[str, Any]
    ) -> Any:
        return await self._decode(value, streams)

    async def decode_output(
        self, value: Any, streams: Dict[str, Any]
    ) -> Any:
        return await self._decode(value, streams)

    async def _encode(
        self, value: Any
    ) -> Tuple[Any, List[str], Dict[str, Dict[str, Any]]]:
        """Run `VariableCodec.encode` with our blob/stream side effects.

        `VariableCodec` inlines every `bytes` value as base64. That's the
        default; we then post-walk the encoded tree and *replace* base64
        markers whose original size exceeds `inline_bytes_threshold` with a
        blob-key marker, offloading the payload to Redis.
        """
        streams: Dict[str, Dict[str, Any]] = {}

        def on_stream_encode(stream_id: str, source: Any, kind: StreamKind) -> None:
            content_type = getattr(source, "content_type", None)
            filename = getattr(source, "filename", None)
            size = getattr(source, "size", None)
            attrs = getattr(source, "attrs", None)
            streams[stream_id] = {
                "kind": kind.value if isinstance(kind, StreamKind) else kind,
                "content_type": content_type,
                "filename": filename,
                "size": size,
                "attrs": dict(attrs) if attrs else None,
                "stream_key": f"{self.stream_prefix}{stream_id}",
                "source": source,
            }

        encoded = self._codec.encode(value, on_stream_encode=on_stream_encode)

        blob_keys: List[str] = []
        try:
            encoded = await self._offload_large_bytes(encoded, blob_keys)
        except BaseException:
            if blob_keys:
                try:
                    await self.client.delete(*blob_keys)
                except BaseException as e:  # pragma: no cover - best effort
                    logging.warning("Failed to cleanup blob keys (%d): %s", len(blob_keys), e)
            raise

        return encoded, blob_keys, streams

    async def _offload_large_bytes(self, node: Any, blob_keys: List[str]) -> Any:
        """Walk the encoded tree; convert oversize inline-bytes markers to blob refs.

        Also enforces `max_blob_size` on the *original* payload size (which
        equals `len(base64.b64decode(value))`). We decode once per marker to
        get the exact byte length.
        """
        import base64

        if isinstance(node, dict):
            variable = node.get("__variable__")

            if len(node) == 1 and isinstance(variable, dict) and variable.get("type") == "bytes":
                if "value" not in variable:
                    return node

                payload = base64.b64decode(variable["value"])

                if self.max_blob_size is not None and len(payload) > self.max_blob_size:
                    raise BlobTooLargeError(f"payload size {len(payload)} exceeds max_blob_size {self.max_blob_size}")

                if len(payload) > self.inline_bytes_threshold:
                    key = f"{self.blob_prefix}{ulid.ulid()}"
                    await self.client.setex(key, self.blob_ttl, payload)
                    blob_keys.append(key)

                    return { "__variable__": { "type": "bytes", "key": key, "size": len(payload) } }

                return node

            return { key: await self._offload_large_bytes(value, blob_keys) for key, value in node.items() }

        if isinstance(node, list):
            return [ await self._offload_large_bytes(value, blob_keys) for value in node ]

        return node

    async def _decode(self, value: Any, streams: Dict[str, Any]) -> Any:
        # First, resolve any blob-key bytes markers to inline base64 so
        # `VariableCodec.decode` can consume them uniformly. This also enforces
        # blob key ownership (must start with our blob_prefix).
        resolved = await self._resolve_blob_refs(value)
        stream_metas: Dict[str, RedisStreamMeta] = {}

        for stream_id, meta in (streams or {}).items():
            if isinstance(meta, RedisStreamMeta):
                stream_metas[stream_id] = meta
            else:
                stream_metas[stream_id] = RedisStreamMeta.deserialize(stream_id, meta)

        def on_stream_decode(variable: Dict[str, Any]) -> Any:
            stream_id = variable.get("id")
            meta = stream_metas.get(stream_id)

            if meta is None:
                # Rebuild a minimal meta from the marker itself when the
                # `streams` section did not carry it (e.g., nested markers
                # inside OBJECT chunks are decoded independently).
                meta = RedisStreamMeta(
                    stream_id=stream_id,
                    kind=StreamKind(variable.get("kind", "bytes")),
                    content_type=variable.get("content_type"),
                    filename=variable.get("filename"),
                    size=variable.get("size"),
                    attrs=variable.get("attrs"),
                    stream_key=f"{self.stream_prefix}{stream_id}",
                )

            if self._stream_factory is None:
                raise RuntimeError("stream_factory is required to decode stream markers")

            return self._stream_factory(meta)

        return self._codec.decode(resolved, on_stream_decode=on_stream_decode)

    async def _resolve_blob_refs(self, node: Any) -> Any:
        """Fetch and inline any bytes markers that reference a blob key."""
        import base64

        if isinstance(node, dict):
            variable = node.get("__variable__")

            if len(node) == 1 and isinstance(variable, dict) and variable.get("type") == "bytes" and "key" in variable:
                key = variable["key"]

                if not isinstance(key, str) or not key.startswith(self.blob_prefix):
                    raise BlobUnauthorizedError(f"blob marker key does not match expected prefix: {key!r}")

                data = await self._consume_blob(key)

                if data is None:
                    raise BlobNotFoundError(f"blob missing or expired: key={key}")

                expected_size = variable.get("size")

                if isinstance(expected_size, int) and len(data) != expected_size:
                    raise BlobCorruptedError(f"size mismatch: expected {expected_size}, got {len(data)} (key={key})")

                return { "__variable__": { "type": "bytes", "value": base64.b64encode(data).decode("ascii") } }

            return { key: await self._resolve_blob_refs(value) for key, value in node.items() }

        if isinstance(node, list):
            return [await self._resolve_blob_refs(value) for value in node]

        return node

    async def _consume_blob(self, key: str) -> Optional[bytes]:
        try:
            return await self.client.execute_command("GETDEL", key)
        except Exception as e:
            # Fall back for Redis versions without GETDEL.
            from redis.exceptions import ResponseError
            if not isinstance(e, ResponseError):
                raise

        async with self.client.pipeline(transaction=True) as pipeline:
            pipeline.get(key)
            pipeline.delete(key)
            data, _ = await pipeline.execute()

        return data
