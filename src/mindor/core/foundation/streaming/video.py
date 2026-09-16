from __future__ import annotations

from typing import Iterable, Union, Optional, Dict, Any, List
from collections.abc import AsyncIterator
from mindor.core.utils.ffmpeg.executable import is_ffmpeg_available
from mindor.core.utils.files import get_file_extension
from mindor.core.utils.pyav import is_available as is_pyav_available
from .resources import StreamResource, TeeStreamResource, AsyncIterableStreamResource
from .bytes import BytesStreamResource
from .file import UploadFileStreamResource
from .media import MediaSource
from starlette.datastructures import UploadFile
from PIL import Image as PILImage

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
    "gif":  "image/gif",
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

    def copyable(self) -> bool:
        return self.source.copyable()

    def copy(self, count: int) -> List[VideoStreamResource]:
        return [
            VideoStreamResource(source, self.format, self.attrs, self.filename)
            for source in self.source.copy(count)
        ]

    def tee(self, sources: List[AsyncIterator[bytes]]) -> List[VideoStreamResource]:
        return [
            VideoStreamResource(
                source=TeeStreamResource(source),
                format=self.format,
                attrs=self.attrs,
                filename=self.filename,
            )
            for source in sources
        ]

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

def encode_frames_to_mp4(
    frames: Iterable[PILImage.Image],
    width: int,
    height: int,
    fps: int,
    codec: str = "libx264",
    pixel_format: str = "yuv420p",
    attrs: Optional[Dict[str, Any]] = None,
    filename: Optional[str] = None,
) -> VideoStreamResource:
    """Encode PIL frames to a fragmented MP4 `VideoStreamResource`.

    Frames are consumed lazily; encoded bytes flow to the consumer as soon as
    the muxer emits each fragment. No raw-frame or full-mp4 buffer is held.

    Backend selection: prefers an ffmpeg subprocess (via `resolve_ffmpeg_executable()`);
    falls back to PyAV (`av`) when neither the system nor imageio-ffmpeg's bundled
    binary is available.
    """
    attrs = { "fps": str(fps), "width": str(width), "height": str(height), **(attrs or {}) }

    async def _stream_mp4_chunks() -> AsyncIterator[bytes]:
        if is_ffmpeg_available():
            from mindor.core.utils.ffmpeg.video import encode_video_from_frames

            async for chunk in encode_video_from_frames(frames, width, height, fps, codec=codec, pixel_format=pixel_format):
                yield chunk

            return

        if is_pyav_available():
            from mindor.core.utils.pyav import encode_video_from_frames

            async for chunk in encode_video_from_frames(frames, width, height, fps, codec=codec, pixel_format=pixel_format):
                yield chunk

            return

        raise RuntimeError(
            "No MP4 encoder available. Install one of: ffmpeg (system), "
            "`pip install imageio-ffmpeg`, or `pip install av`."
        )

    return VideoStreamResource(
        source=AsyncIterableStreamResource(_stream_mp4_chunks()),
        format="mp4",
        attrs=attrs,
        filename=filename,
    )

def create_video_source(value: Any) -> MediaSource:
    if isinstance(value, VideoStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, StreamResource):
        if getattr(value, "filename", None):
            return MediaSource(value, format=get_file_extension(getattr(value, "filename")))
        else:
            return MediaSource(value)

    if isinstance(value, UploadFile):
        if value.filename:
            return MediaSource(UploadFileStreamResource(value), format=get_file_extension(value.filename))
        else:
            return MediaSource(UploadFileStreamResource(value))

    if isinstance(value, (bytes, bytearray)):
        return MediaSource(BytesStreamResource(bytes(value)))

    raise TypeError(f"Unsupported video source: {value.__class__.__name__}")
