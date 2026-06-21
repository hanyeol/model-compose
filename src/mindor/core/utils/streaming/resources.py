from typing import Optional, List, Protocol, Union, Awaitable, runtime_checkable
from collections.abc import AsyncIterator, AsyncIterable
from abc import ABC, abstractmethod
from ..files import create_temporary_file
import aiofiles, io

@runtime_checkable
class BytesReader(Protocol):
    def read(self, size: int, /) -> Union[bytes, Awaitable[bytes]]: ...

@runtime_checkable
class ClosableBytesReader(BytesReader, Protocol):
    def close(self) -> Union[None, Awaitable[None]]: ...

@runtime_checkable
class ClosableAsyncIterable(AsyncIterable, Protocol):
    def aclose(self) -> Awaitable[None]: ...

class StreamResource(ABC):
    def __init__(self, content_type: Optional[str], filename: Optional[str], size: Optional[int] = None):
        self.content_type = content_type or "application/octet-stream"
        self.filename = filename
        self.size: Optional[int] = size

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __aiter__(self):
        return self._iterate_stream()

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        pass

class ReaderStreamResource(StreamResource):
    def __init__(
        self,
        reader: BytesReader,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        chunk_size: int = 8192,
        size: Optional[int] = None
    ):
        super().__init__(content_type, filename, size=size)

        self.reader: BytesReader = reader
        self.chunk_size: int = chunk_size

    async def close(self) -> None:
        if isinstance(self.reader, ClosableBytesReader):
            try:
                result = self.reader.close()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        while True:
            chunk = self.reader.read(self.chunk_size)
            if hasattr(chunk, "__await__"):
                chunk = await chunk
            if not chunk:
                break
            yield chunk

class AsyncIterableStreamResource(StreamResource):
    def __init__(
        self,
        source: AsyncIterable,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        size: Optional[int] = None
    ):
        super().__init__(content_type, filename, size=size)

        self.source: AsyncIterable = source

    async def close(self) -> None:
        if isinstance(self.source, ClosableAsyncIterable):
            try:
                await self.source.aclose()
            except Exception:
                pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            if chunk is None:
                continue
            if isinstance(chunk, str):
                yield chunk.encode("utf-8")
            else:
                yield bytes(chunk)

class ChunkedStreamResource(StreamResource):
    def __init__(self, stream: StreamResource, chunk_size: int):
        super().__init__(stream.content_type, stream.filename, size=stream.size)

        self.stream: StreamResource = stream
        self.chunk_size: int = chunk_size

    async def close(self) -> None:
        await self.stream.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        buffer = bytearray()

        async for chunk in self.stream:
            buffer.extend(chunk)
            while len(buffer) >= self.chunk_size:
                yield bytes(buffer[:self.chunk_size])
                del buffer[:self.chunk_size]

        if buffer:
            yield bytes(buffer)

async def read_stream_to_buffer(stream: StreamResource) -> io.BytesIO:
    buffer = io.BytesIO()
    async with stream:
        async for chunk in stream:
            buffer.write(chunk)
    buffer.seek(0)
    return buffer

async def read_stream_to_bytes(stream: StreamResource) -> bytes:
    chunks: List[bytes] = []
    async with stream:
        async for chunk in stream:
            chunks.append(chunk)
    return b"".join(chunks)

async def save_stream_to_file(stream: StreamResource, path: str) -> None:
    async with stream, aiofiles.open(path, "wb") as file:
        async for chunk in stream:
            await file.write(chunk)

async def save_stream_to_temporary_file(stream: StreamResource, extension: Optional[str]) -> Optional[str]:
    path = create_temporary_file(extension)
    async with stream, aiofiles.open(path, "wb") as file:
        async for chunk in stream:
            await file.write(chunk)
    return path
