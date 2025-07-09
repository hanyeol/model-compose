from typing import Optional, AsyncIterator
from abc import ABC, abstractmethod
from tempfile import NamedTemporaryFile
from aiofiles.threadpool.binary import AsyncBufferedReader
import aiofiles, os, io, base64

class StreamResource(ABC):
    def __init__(self, content_type: Optional[str], filename: Optional[str]):
        self.content_type = content_type or "application/octet-stream"
        self.filename = filename

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
    def __init__(self, path: str, content_type: Optional[str] = None, filename: Optional[str] = None):
        super().__init__(content_type, filename or os.path.basename(path))

        self.path = path
        self.stream: Optional[aiofiles.threadpool.text.AsyncTextIOWrapper] = None

    async def __aenter__(self):
        self.stream = await aiofiles.open(self.path, "rb")
        return self

    async def close(self) -> None:
        if self.stream:
            await self.stream.close()
            self.stream = None
        
    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self.stream.read(8192)
            if not chunk:
                break
            yield chunk

class Base64StreamResource(StreamResource):
    def __init__(self, encoded: str, content_type: Optional[str] = None, filename: Optional[str] = None):
        super().__init__(content_type, filename)

        self.encoded: str = encoded
        self.stream: Optional[io.BytesIO] = None

    async def __aenter__(self):
        self.stream = io.BytesIO(base64.b64decode(self.encoded))
        return self

    async def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        while True:
            chunk = self.stream.read(8192)
            if not chunk:
                break
            yield chunk

async def save_stream_to_temporary_file(stream: StreamResource, extension: Optional[str]) -> Optional[str]:
    try:
        file = NamedTemporaryFile(suffix=f".{extension}" if extension else None, delete=False)
        async with stream:
            async for chunk in stream:
                file.write(chunk)
        file.flush()
        file.close()
        return file.name
    except Exception:
        return None

async def encode_stream_to_base64(stream: StreamResource) -> str:
    buffer = io.BytesIO()
    async with stream:
        async for chunk in stream:
            buffer.write(chunk)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")
