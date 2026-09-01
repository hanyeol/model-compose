from __future__ import annotations

from typing import Optional, Any, List
from collections.abc import AsyncIterator
from .resources import StreamResource, read_stream_to_bytes
from .resolver import resolve_stream_resource
import asyncio, base64, io

# Payloads smaller than this stay on the event loop; larger ones are offloaded
# to a thread so multi-MB base64 conversions don't stall the loop. ~40µs of
# to_thread overhead ≈ 16 KB at typical b64 throughput (~500 MB/s).
_OFFLOAD_THRESHOLD_BYTES = 16 * 1024

class Base64StreamResource(StreamResource):
    def __init__(
        self,
        data: str,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        chunk_size: int = 8192
    ):
        super().__init__(content_type, filename, size=self._decoded_size(data))

        self.data: str = data
        self.chunk_size: int = chunk_size
        self._stream: Optional[io.BytesIO] = None

    def copyable(self) -> bool:
        return True

    def copy(self, count: int) -> List["Base64StreamResource"]:
        return [
            Base64StreamResource(self.data, self.content_type, self.filename, self.chunk_size)
            for _ in range(count)
        ]

    async def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._stream:
            self._stream = io.BytesIO(await decode_base64(self.data))

        while True:
            chunk = self._stream.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

    @staticmethod
    def _decoded_size(data: str) -> int:
        padding = 2 if data.endswith("==") else (1 if data.endswith("=") else 0)
        return (len(data) // 4) * 3 - padding

async def encode_value_to_base64(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return await encode_base64(bytes(value))

    if isinstance(value, str):
        return await encode_base64(value.encode("utf-8"))

    if not isinstance(value, StreamResource):
        value = await resolve_stream_resource(value)

    return await encode_stream_to_base64(value)

async def encode_stream_to_base64(stream: StreamResource) -> str:
    return await encode_base64(await read_stream_to_bytes(stream))

async def encode_base64(data: bytes) -> str:
    if len(data) < _OFFLOAD_THRESHOLD_BYTES:
        return base64.b64encode(data).decode("ascii")

    return await asyncio.to_thread(lambda: base64.b64encode(data).decode("ascii"))

async def decode_base64_value(value: Any) -> bytes:
    if isinstance(value, str):
        return await decode_base64(value)

    if isinstance(value, (bytes, bytearray)):
        return await decode_base64(bytes(value).decode("ascii"))

    if not isinstance(value, StreamResource):
        value = await resolve_stream_resource(value)

    return await decode_base64_stream(value)

async def decode_base64_stream(stream: StreamResource) -> bytes:
    return await decode_base64((await read_stream_to_bytes(stream)).decode("ascii"))

async def decode_base64(data: str) -> bytes:
    if len(data) < _OFFLOAD_THRESHOLD_BYTES:
        return base64.b64decode(data)

    return await asyncio.to_thread(base64.b64decode, data)
