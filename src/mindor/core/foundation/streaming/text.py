from __future__ import annotations

from typing import Optional, List
from collections.abc import AsyncIterable, AsyncIterator
from .resources import StreamResource, read_stream_to_bytes
import asyncio, io

# utf-8 decode is very fast (~2 GB/s), so break-even against ~40µs of
# to_thread overhead sits around 128 KB. Small payloads stay on the loop.
_OFFLOAD_THRESHOLD_BYTES = 128 * 1024

class TextStreamResource(StreamResource):
    def __init__(self, text: str, encoding: str = "utf-8", filename: Optional[str] = None):
        super().__init__(self._resolve_content_type(encoding), filename)

        self.text: str = text
        self.encoding: str = encoding
        self.buffer: Optional[io.BytesIO] = None

    def copyable(self) -> bool:
        return True

    def copy(self, count: int) -> List[TextStreamResource]:
        return [
            TextStreamResource(self.text, self.encoding, self.filename)
            for _ in range(count)
        ]

    async def close(self) -> None:
        if self.buffer:
            self.buffer.close()
            self.buffer = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self.buffer:
            self.buffer = io.BytesIO(self.text.encode(self.encoding))

        while True:
            chunk = self.buffer.read(8192)
            if not chunk:
                break
            yield chunk

    def _resolve_content_type(self, encoding: str) -> str:
        return f"text/plain; charset={encoding}"

async def load_text_from_stream(stream: StreamResource, encoding: str = "utf-8") -> str:
    if isinstance(stream, TextStreamResource):
        return stream.text

    data = await read_stream_to_bytes(stream)

    if len(data) < _OFFLOAD_THRESHOLD_BYTES:
        return data.decode(encoding, errors="replace")

    return await asyncio.to_thread(lambda: data.decode(encoding, errors="replace"))

async def load_text_from_iterator(iterator: AsyncIterable, encoding: str = "utf-8") -> str:
    parts: list[str] = []

    async for chunk in iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode(encoding, errors="replace")
        parts.append(chunk)

    return "".join(parts)
