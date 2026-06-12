from typing import Any, Optional, List, Protocol, Union, Awaitable, runtime_checkable
from collections.abc import AsyncIterator, AsyncIterable
from abc import ABC, abstractmethod
from enum import Enum
from .files import create_temporary_file
from starlette.datastructures import UploadFile
import aiofiles, os, io, base64, json

@runtime_checkable
class BytesReader(Protocol):
    def read(self, size: int, /) -> Union[bytes, Awaitable[bytes]]: ...

@runtime_checkable
class ClosableBytesReader(BytesReader, Protocol):
    def close(self) -> Union[None, Awaitable[None]]: ...

class StreamFormat(str, Enum):
    TEXT = "text"
    JSON = "json"

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

class FileStreamResource(StreamResource):
    def __init__(
        self,
        path: str,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        chunk_size: int = 8192,
        auto_delete: bool = False
    ):
        super().__init__(content_type, filename or os.path.basename(path), size=os.path.getsize(path))

        self.path = path
        self.chunk_size: int = chunk_size
        self.auto_delete: bool = auto_delete
        self.stream: Optional[aiofiles.threadpool.text.AsyncTextIOWrapper] = None

    async def close(self) -> None:
        if self.stream:
            await self.stream.close()
            self.stream = None
        if self.auto_delete:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self.stream:
            self.stream = await aiofiles.open(self.path, "rb")

        while True:
            chunk = await self.stream.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

class UploadFileStreamResource(StreamResource):
    def __init__(self, file: UploadFile):
        super().__init__(file.content_type, file.filename, size=file.size)

        self.file: UploadFile = file

    async def close(self) -> None:
        await self.file.seek(0)

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        await self.file.seek(0)
        while True:
            chunk = await self.file.read(8192)
            if not chunk:
                break
            yield chunk

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
        self.stream: Optional[io.BytesIO] = None
        self.chunk_size: int = chunk_size

    async def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self.stream:
            self.stream = io.BytesIO(self.data)

        while True:
            chunk = self.stream.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

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
        self.stream: Optional[io.BytesIO] = None
        self.chunk_size: int = chunk_size

    async def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self.stream:
            self.stream = io.BytesIO(base64.b64decode(self.data))

        while True:
            chunk = self.stream.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

    @staticmethod
    def _decoded_size(data: str) -> int:
        padding = 2 if data.endswith("==") else (1 if data.endswith("=") else 0)
        return (len(data) // 4) * 3 - padding

class EventStreamResource(StreamResource):
    def __init__(
        self,
        iterator: AsyncIterable,
        format: Optional[StreamFormat] = None
    ):
        super().__init__("text/event-stream", None)

        self.iterator: Optional[AsyncIterable] = iterator
        self.format: Optional[StreamFormat] = format

    async def close(self):
        self.iterator = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.iterator:
            if chunk is not None:
                encoded = self._encode_chunk(chunk)
                for line in self._split_chunk(encoded):
                    yield b"data: " + line + b"\n"
                yield b"\n"

    def _encode_chunk(self, chunk: Any) -> Any:
        if self.format == StreamFormat.TEXT:
            return chunk if isinstance(chunk, str) else str(chunk)
        if self.format == StreamFormat.JSON:
            return json.dumps(chunk, ensure_ascii=False, default=str)
        if not isinstance(chunk, (str, bytes)):
            return json.dumps(chunk, ensure_ascii=False, default=str)
        return chunk

    def _split_chunk(self, chunk: Any) -> List[bytes]:
        if isinstance(chunk, str):
            return [ line.encode("utf-8") for line in chunk.split("\n") ]
        if isinstance(chunk, bytes):
            return [ line for line in chunk.split(b"\n") ]
        return [ chunk ]

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

async def resolve_stream_resource(source: Any) -> StreamResource:
    if isinstance(source, StreamResource):
        return source

    if isinstance(source, UploadFile):
        return UploadFileStreamResource(source)

    if isinstance(source, (bytes, bytearray)):
        return BytesStreamResource(bytes(source))

    if isinstance(source, str):
        return BytesStreamResource(source.encode("utf-8"), content_type="text/plain")

    if isinstance(source, BytesReader):
        return ReaderStreamResource(source)

    raise TypeError(f"Unsupported source type: {type(source).__name__}")

async def decode_event_stream(stream: StreamResource) -> AsyncIterator[bytes]:
    buffer = bytearray()

    async for chunk in stream:
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

async def encode_stream_to_base64(stream: StreamResource) -> str:
    buffer = io.BytesIO()
    async with stream:
        async for chunk in stream:
            buffer.write(chunk)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")

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
