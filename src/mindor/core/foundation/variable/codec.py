from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union
from collections.abc import AsyncIterator
from enum import Enum
from pydantic import BaseModel
from ..streaming.resources import StreamResource
from ..streaming.iterators import StreamIterator, StreamEncodingIterator, StreamEncodingFormat
from ..streaming.image import ImageStreamResource
from PIL import Image as PILImage
import base64, ulid

class StreamKind(str, Enum):
    """Wire representation of stream chunk data."""
    BYTES  = "bytes"
    TEXT   = "text"
    OBJECT = "object"

StreamEncodeCallback = Callable[[str, Any, StreamKind], None]
StreamDecodeCallback = Callable[[Dict[str, Any]], Any]

class VariableCodec:
    """Codec for workflow variable values.

    Transforms a value tree of input/output variables into a JSON-compatible
    dict (and back), wrapping non-JSON-native values in `__variable__` markers:

    - `bytes` / `bytearray` → `{"__variable__": {"type": "bytes", "value": "<b64>"}}`
      with the data inlined as base64.
    - `StreamResource`, `StreamIterator`, `AsyncIterator`, `PIL.Image` →
      `{"__variable__": {"type": "stream", "id": "<ulid>", "kind": ...,
      "content_type": ..., ...}}`. Actual chunk data is shipped separately via
      `STREAM_*` messages (out of scope for the codec itself).
    - JSON-native scalars/containers and `pydantic.BaseModel` (via `model_dump`)
      pass through directly.
    - Anything else raises `TypeError` at encode time.

    The codec does NOT handle byte-level serialization — callers (e.g.,
    `IpcMessage.serialize`) take the encoded dict and produce wire bytes.

    The codec does NOT track stream registries; callers supply `on_stream_encode`
    / `on_stream_decode` callbacks to bridge to a dispatcher. `on_stream_decode`
    is required whenever the wire contains stream variables — decoding raises
    `RuntimeError` otherwise.
    """
    def encode(
        self,
        value: Any,
        on_stream_encode: Optional[StreamEncodeCallback] = None,
    ) -> Any:
        return self._encode_value(value, on_stream_encode)

    def decode(
        self,
        value: Any,
        on_stream_decode: Optional[StreamDecodeCallback] = None,
    ) -> Any:
        return self._decode_value(value, on_stream_decode)

    def _encode_value(self, value: Any, on_stream_encode: Optional[StreamEncodeCallback]) -> Any:
        # JSON-native scalars
        if value is None or isinstance(value, (bool, int, float, str)):
            return value

        # BaseModel → model_dump(mode="json")
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")

        # bytes-like → inline variable
        if isinstance(value, (bytes, bytearray)):
            return self._build_bytes_variable(bytes(value))

        # PIL.Image auto-lift to ImageStreamResource
        if isinstance(value, PILImage.Image):
            return self._build_stream_variable(ImageStreamResource(value), on_stream_encode)

        # Streams (StreamResource, StreamIterator subclasses, generic AsyncIterator)
        if isinstance(value, (StreamIterator, AsyncIterator, StreamResource)):
            return self._build_stream_variable(value, on_stream_encode)

        # Containers (after stream checks so that stream classes don't fall through here)
        if isinstance(value, dict):
            return { str(k): self._encode_value(v, on_stream_encode) for k, v in value.items() }

        if isinstance(value, (list, tuple)):
            return [ self._encode_value(v, on_stream_encode) for v in value ]

        raise TypeError(f"Cannot serialize value of type {type(value).__name__}")

    def _build_bytes_variable(self, data: bytes) -> Dict[str, Any]:
        return {
            "__variable__": {
                "type": "bytes",
                "value": base64.b64encode(data).decode("ascii"),
            }
        }

    def _build_stream_variable(
        self,
        source: Any,
        on_stream_encode: Optional[StreamEncodeCallback],
    ) -> Dict[str, Any]:
        stream_id = ulid.ulid()
        kind = self._classify_stream_kind(source)
        variable: Dict[str, Any] = {
            "type": "stream",
            "id": stream_id,
            "kind": kind.value,
        }

        if isinstance(source, StreamResource):
            variable["content_type"] = source.content_type
            variable["filename"] = source.filename
            variable["size"] = source.size
            attrs = getattr(source, "attrs", None)
            if attrs:
                variable["attrs"] = dict(attrs)

        if on_stream_encode is not None:
            on_stream_encode(stream_id, source, kind)

        return { "__variable__": variable }

    def _classify_stream_kind(self, source: Any) -> StreamKind:
        if isinstance(source, StreamEncodingIterator):
            if source.format == StreamEncodingFormat.TEXT:
                return StreamKind.TEXT
            if source.format == StreamEncodingFormat.JSON:
                return StreamKind.OBJECT
            return StreamKind.OBJECT

        if isinstance(source, StreamResource):
            return StreamKind.BYTES

        return StreamKind.OBJECT

    def _decode_value(self, value: Any, on_stream_decode: Optional[StreamDecodeCallback]) -> Any:
        if isinstance(value, dict):
            variable = value.get("__variable__")
            if len(value) == 1 and isinstance(variable, dict) and isinstance(variable.get("type"), str):
                return self._resolve_variable(variable, on_stream_decode)
            return { k: self._decode_value(v, on_stream_decode) for k, v in value.items() }

        if isinstance(value, list):
            return [ self._decode_value(v, on_stream_decode) for v in value ]

        return value

    def _resolve_variable(
        self,
        variable: Dict[str, Any],
        on_stream_decode: Optional[StreamDecodeCallback],
    ) -> Any:
        variable_type = variable.get("type")

        if variable_type == "bytes":
            value = variable.get("value", "")
            if not isinstance(value, str):
                raise ValueError(f"Invalid bytes variable: 'value' must be a string, got {type(value).__name__}")
            return base64.b64decode(value)

        if variable_type == "stream":
            if on_stream_decode is None:
                raise RuntimeError("on_stream_decode callback is required to decode stream variables")
            return on_stream_decode(variable)

        raise ValueError(f"Unknown variable type: {variable_type!r}")
