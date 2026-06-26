from typing import Optional
from collections.abc import AsyncIterator
from .resources import StreamResource
from starlette.datastructures import UploadFile
import aiofiles, os

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
        self._stream: Optional[aiofiles.threadpool.text.AsyncTextIOWrapper] = None

    async def close(self) -> None:
        if self._stream:
            await self._stream.close()
            self._stream = None
        if self.auto_delete:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._stream:
            self._stream = await aiofiles.open(self.path, "rb")

        while True:
            chunk = await self._stream.read(self.chunk_size)
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
