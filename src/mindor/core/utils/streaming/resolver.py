from typing import Any
from collections.abc import AsyncIterable
from .resources import StreamResource, BytesReader, ReaderStreamResource, AsyncIterableStreamResource
from .file import UploadFileStreamResource
from .bytes import BytesStreamResource
from .text import TextStreamResource
from .image import ImageStreamResource
from starlette.datastructures import UploadFile
from PIL import Image as PILImage

async def resolve_stream_resource(value: Any) -> StreamResource:
    if isinstance(value, StreamResource):
        return value

    if isinstance(value, AsyncIterable):
        return AsyncIterableStreamResource(value, content_type=getattr(value, "content_type", None))

    if isinstance(value, UploadFile):
        return UploadFileStreamResource(value)

    if isinstance(value, PILImage.Image):
        return ImageStreamResource(value)

    if isinstance(value, (bytes, bytearray)):
        return BytesStreamResource(bytes(value))

    if isinstance(value, str):
        return TextStreamResource(value)

    if isinstance(value, BytesReader):
        return ReaderStreamResource(value)

    raise TypeError(f"Unsupported value type: {type(value).__name__}")
