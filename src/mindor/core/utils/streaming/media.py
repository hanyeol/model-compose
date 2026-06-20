from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from .stream import StreamResource
from .bytes import BytesStreamResource
from .file import FileStreamResource, UploadFileStreamResource
from starlette.datastructures import UploadFile

@dataclass
class MediaSource:
    stream: StreamResource
    format: Optional[str] = None
    attrs: Dict[str, Any] = field(default_factory=dict)

def create_media_source(value: Any) -> MediaSource:
    from .audio import PcmStreamResource, WavStreamResource, AudioStreamResource
    from .video import VideoStreamResource

    if isinstance(value, VideoStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, PcmStreamResource):
        return MediaSource(value.samples, value.format, value.attrs)

    if isinstance(value, WavStreamResource):
        return MediaSource(value, "wav", value.attrs)

    if isinstance(value, AudioStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, StreamResource):
        return MediaSource(value)

    if isinstance(value, UploadFile):
        return MediaSource(UploadFileStreamResource(value))

    if isinstance(value, (bytes, bytearray)):
        return MediaSource(BytesStreamResource(bytes(value)))

    if isinstance(value, str):
        return MediaSource(FileStreamResource(value))

    raise TypeError(f"Unsupported media source: {value.__class__.__name__}")
