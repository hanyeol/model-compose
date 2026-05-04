from typing import Optional, Any
from collections.abc import AsyncIterator, AsyncIterable
from .streaming import StreamFormat
import json

class HttpEventStreamer:
    def __init__(self, iterator: AsyncIterable, format: Optional[StreamFormat] = None):
        self.iterator: AsyncIterable = iterator
        self.format: Optional[StreamFormat] = format

    async def stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.iterator:
            chunk = self._encode_chunk(chunk, self.format)

            if chunk is None:
                continue

            for line in self._split_chunk(chunk):
                yield b"data: " + line + b"\n"

            yield b"\n"

    def _encode_chunk(self, chunk: Any, format: Optional[StreamFormat]) -> Optional[str]:
        if format == StreamFormat.TEXT:
            return str(chunk) if not isinstance(chunk, str) else chunk

        if format == StreamFormat.JSON:
            return json.dumps(chunk, ensure_ascii=False, default=str)

        if not isinstance(chunk, (str, bytes, type(None))):
            return json.dumps(chunk, ensure_ascii=False, default=str)

        return chunk

    def _split_chunk(self, chunk: Any) -> list[bytes]:
        if isinstance(chunk, str):
            if chunk.endswith("\n"):
                lines = chunk[:-1].split("\n")
                if chunk.startswith("\n"):
                    lines = [""] + lines
                return [ line.encode("utf-8") for line in lines ]
            return [ chunk.encode("utf-8") ]

        if isinstance(chunk, bytes):
            return [ chunk ]

        return [ chunk ]
