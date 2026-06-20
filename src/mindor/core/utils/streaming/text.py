from typing import Optional
from collections.abc import AsyncIterator
from .stream import StreamResource, read_stream_to_bytes
import io

class TextStreamResource(StreamResource):
    def __init__(self, text: str, encoding: str = "utf-8", filename: Optional[str] = None):
        super().__init__(self._resolve_content_type(encoding), filename)

        self.text: str = text
        self.encoding: str = encoding
        self.buffer: Optional[io.BytesIO] = None

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

    return (await read_stream_to_bytes(stream)).decode(encoding, errors="replace")
