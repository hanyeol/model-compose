from typing import Optional, AsyncIterator
from .streaming import StreamResource
from PIL import Image as PILImage
import io

_content_type_map = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg", 
    "webp": "image/webp",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "ico": "image/x-icon"
}

_pil_format_map = {
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
        self.buffer: Optional[io.BytesIO] = None
    
    async def close(self) -> None:
        if self.buffer:
            self.buffer.close()
            self.buffer = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self.buffer:
            self.buffer = io.BytesIO()
            self.image.save(self.buffer, self._resolve_pil_format(self.format))
            self.buffer.seek(0)

        while True:
            chunk = self.buffer.read(8192)  # Read in 8KB chunks
            if not chunk:
                break
            yield chunk

    def _resolve_content_type(self, format: str) -> str:
        return _content_type_map.get(format, "application/octet-stream")
    
    def _resolve_pil_format(self, format: str) -> str:
        return _pil_format_map.get(format, "PNG")

async def load_image_from_stream(stream: StreamResource, extension: Optional[str] = None) -> Optional[PILImage.Image]:
    try:
        data = bytearray()
        async with stream:
            async for chunk in stream:
                data.extend(chunk)
            return PILImage.open(io.BytesIO(data))
    except Exception as e:
        return None
