from typing import Union, Optional, Dict, Any
from collections.abc import AsyncIterator
from .stream import StreamResource
from .bytes import BytesStreamResource
from .file import UploadFileStreamResource
from .media import MediaSource
from starlette.datastructures import UploadFile

_VIDEO_CONTENT_TYPE_MAP: Dict[str, str] = {
    "mp4":  "video/mp4",
    "m4v":  "video/mp4",
    "mov":  "video/quicktime",
    "webm": "video/webm",
    "mkv":  "video/x-matroska",
    "avi":  "video/x-msvideo",
    "flv":  "video/x-flv",
    "wmv":  "video/x-ms-wmv",
    "mpeg": "video/mpeg",
    "mpg":  "video/mpeg",
    "ts":   "video/mp2t",
    "3gp":  "video/3gpp",
    "ogv":  "video/ogg",
}

class VideoStreamResource(StreamResource):
    def __init__(
        self,
        source: Union[StreamResource, bytes],
        format: Optional[str] = None,
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__(self._resolve_content_type(format), filename, size=self._resolve_size(source))

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.format: Optional[str] = format
        self.attrs: Dict[str, Any] = attrs or {}

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            yield chunk

    @staticmethod
    def _resolve_content_type(format: Optional[str]) -> str:
        if format:
            return _VIDEO_CONTENT_TYPE_MAP.get(format.lower(), "application/octet-stream")

        return "application/octet-stream"

    @staticmethod
    def _resolve_size(source: Union[StreamResource, bytes]) -> Optional[int]:
        return source.size if isinstance(source, StreamResource) else len(source)

def create_video_source(value: Any) -> MediaSource:
    if isinstance(value, VideoStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, StreamResource):
        return MediaSource(value)

    if isinstance(value, UploadFile):
        return MediaSource(UploadFileStreamResource(value))

    if isinstance(value, (bytes, bytearray)):
        return MediaSource(BytesStreamResource(bytes(value)))

    raise TypeError(f"Unsupported video source: {value.__class__.__name__}")
