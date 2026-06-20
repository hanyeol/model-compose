from typing import Optional
from collections.abc import AsyncIterator
from .stream import StreamResource
import io

class BytesStreamResource(StreamResource):
    def __init__(
        self,
        data: bytes,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        chunk_size: int = 8192
    ):
        super().__init__(content_type, filename, size=len(data))

        self.data: bytes = data
        self.chunk_size: int = chunk_size
        self._stream: Optional[io.BytesIO] = None

    async def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._stream:
            self._stream = io.BytesIO(self.data)

        while True:
            chunk = self._stream.read(self.chunk_size)
            if not chunk:
                break
            yield chunk
