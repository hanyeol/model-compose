from __future__ import annotations

from typing import Optional, List, Union
from collections.abc import AsyncIterator
from .resources import StreamResource
from PIL import Image as PILImage
import asyncio, io

_CONTENT_TYPE_MAP = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "ico": "image/x-icon"
}

_PIL_FORMAT_MAP = {
    "png": "PNG",
    "jpeg": "JPEG",
    "jpg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "gif": "GIF",
    "tiff": "TIFF",
    "ico": "ICO"
}

class ImageStreamResource(StreamResource):
    def __init__(
        self,
        image: Union[PILImage.Image, bytes],
        format: str = "png",
        filename: Optional[str] = None,
        chunk_size: int = 8192,
    ):
        super().__init__(self._resolve_content_type(format), filename)

        self.image: Union[PILImage.Image, bytes] = image
        self.format: str = format
        self.chunk_size: int = chunk_size
        self._stream: Optional[io.BytesIO] = None

    async def as_image(self) -> PILImage.Image:
        if isinstance(self.image, bytes):
            def _decode(data: bytes) -> PILImage.Image:
                image = PILImage.open(io.BytesIO(data))
                image.load()

                return image

            self.image = await asyncio.to_thread(_decode, self.image)

        return self.image

    def copyable(self) -> bool:
        return True

    def copy(self, count: int) -> List[ImageStreamResource]:
        return [
            ImageStreamResource(self.image, self.format, self.filename, self.chunk_size)
            for _ in range(count)
        ]

    async def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if self._stream is None:
            if isinstance(self.image, bytes):
                self._stream = io.BytesIO(self.image)
            else:
                self._stream = await asyncio.to_thread(self._encode_to_buffer, self.image, self.format)

        while True:
            chunk = self._stream.read(self.chunk_size)

            if not chunk:
                break

            yield chunk

    def _encode_to_buffer(self, image: PILImage.Image, format: str) -> io.BytesIO:
        buffer = io.BytesIO()
        image.save(buffer, self._resolve_pil_format(format))
        buffer.seek(0)

        return buffer

    def _resolve_content_type(self, format: str) -> str:
        return _CONTENT_TYPE_MAP.get(format, "application/octet-stream")

    def _resolve_pil_format(self, format: str) -> str:
        return _PIL_FORMAT_MAP.get(format, "PNG")

async def load_image_from_stream(stream: StreamResource) -> PILImage.Image:
    data = bytearray()

    async with stream:
        async for chunk in stream:
            data.extend(chunk)

    return await asyncio.to_thread(PILImage.open, io.BytesIO(data))

async def load_image_from_bytes(data: bytes) -> PILImage.Image:
    def _open():
        image = PILImage.open(io.BytesIO(data))
        image.load()

        return image

    return await asyncio.to_thread(_open)
