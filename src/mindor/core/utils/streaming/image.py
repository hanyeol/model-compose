from typing import Optional
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
    def __init__(self, image: PILImage.Image, format: str = "png", filename: Optional[str] = None):
        super().__init__(self._resolve_content_type(format), filename)

        self.image: PILImage.Image = image
        self.format: str = format
        self._buffer: Optional[io.BytesIO] = None

    async def close(self) -> None:
        if self._buffer:
            self._buffer.close()
            self._buffer = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._buffer:
            self._buffer = await asyncio.to_thread(self._write_to_buffer, self.image, self.format)

        while True:
            chunk = self._buffer.read(8192)  # Read in 8KB chunks
            if not chunk:
                break
            yield chunk

    def _write_to_buffer(self, image: PILImage.Image, format: str) -> io.BytesIO:
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
    return PILImage.open(io.BytesIO(data))
