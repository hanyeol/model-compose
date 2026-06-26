from typing import List, Any
from collections.abc import AsyncIterator, AsyncIterable

class HttpEventStreamer:
    def __init__(self, iterator: AsyncIterable):
        self.iterator: AsyncIterable = iterator

    async def stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.iterator:
            if chunk is None:
                continue

            for line in self._split_chunk(chunk):
                yield b"data: " + line + b"\n"

            yield b"\n"

    def _split_chunk(self, chunk: Any) -> List[bytes]:
        if isinstance(chunk, str):
            return [ line.encode("utf-8") for line in chunk.split("\n") ]

        if isinstance(chunk, bytes):
            return [ line for line in chunk.split(b"\n") ]

        return [ chunk ]
