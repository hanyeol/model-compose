from typing import Optional, List, Any
from collections.abc import AsyncIterator, AsyncIterable
from .streaming.resources import StreamResource
import aiohttp

class HttpReaderStreamResource(StreamResource):
    def __init__(
        self,
        response: aiohttp.ClientResponse,
        content_type: Optional[str] = None,
        filename: Optional[str] = None
    ):
        super().__init__(content_type, filename)

        self.response: aiohttp.ClientResponse = response
        self.stream: aiohttp.StreamReader = response.content

    async def close(self) -> None:
        self.response.close()
        self.response = None
        self.stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        _, buffer_size = self.stream.get_read_buffer_limits()
        chunk_size = buffer_size or 65536

        while not self.stream.at_eof():
            chunk = await self.stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

class HttpStreamResource(StreamResource):
    def __init__(
        self,
        response: aiohttp.ClientResponse,
        content_type: Optional[str] = None,
        filename: Optional[str] = None
    ):
        super().__init__(content_type, filename)

        self.source: HttpReaderStreamResource = HttpReaderStreamResource(response, content_type, filename)

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            yield chunk

class HttpEventStreamResource(StreamResource):
    def __init__(self, response: aiohttp.ClientResponse):
        super().__init__(None, None)

        self.source: HttpReaderStreamResource = HttpReaderStreamResource(response)

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        buffer = bytearray()

        async for chunk in self.source:
            buffer += chunk.replace(b"\r\n", b"\n")

            while True:
                pos = buffer.find(b"\n\n")
                if pos < 0:
                    break

                block, buffer = buffer[:pos], buffer[pos + 2:]
                parts = []

                for line in block.split(b"\n"):
                    if line.startswith(b"data:"):
                        parts.append(line[6:] if line[5:6] == b" " else line[5:])
                        continue
                    if line == b"data":
                        parts.append(b"")
                        continue
                    if line.startswith(b":"): # comment
                        continue

                if parts:
                    yield b"\n".join(parts)

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
