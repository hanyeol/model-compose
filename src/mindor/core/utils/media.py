from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from .streaming import StreamResource, BytesStreamResource, UploadFileStreamResource
from starlette.datastructures import UploadFile

@dataclass
class MediaSource:
    """
    Normalized media input fed to converter drivers.

    - stream: raw byte stream
    - format: ffmpeg input format identifier (e.g. 's16le', 'mp3', 'rawvideo')
    - attrs:  extra ffmpeg-vocabulary parameters (sample_rate, channels, resolution, fps, pixel_format, ...)
    """
    stream: StreamResource
    format: Optional[str] = None
    attrs: Dict[str, Any] = field(default_factory=dict)

def create_media_source(value: Any) -> MediaSource:
    from .audio import PcmStreamResource, WavStreamResource, AudioStreamResource
    from .video import VideoStreamResource
    from .streaming import FileStreamResource

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
