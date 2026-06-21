from typing import Optional, Any
from collections.abc import AsyncIterator
from .resources import StreamResource, read_stream_to_bytes
from .resolver import resolve_stream_resource
import base64, io

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

    async def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._stream:
            self._stream = io.BytesIO(base64.b64decode(self.data))

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
        return base64.b64encode(bytes(value)).decode("ascii")

    if isinstance(value, str):
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    if not isinstance(value, StreamResource):
        value = await resolve_stream_resource(value)

    return await encode_stream_to_base64(value)

async def encode_stream_to_base64(stream: StreamResource) -> str:
    return base64.b64encode(await read_stream_to_bytes(stream)).decode("ascii")
