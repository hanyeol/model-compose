from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from mindor.core.utils.files import get_file_extension
from .resources import StreamResource
from .bytes import BytesStreamResource
from .file import UploadFileStreamResource
from starlette.datastructures import UploadFile

@dataclass
class MediaSource:
    stream: StreamResource
    format: Optional[str] = None
    attrs: Dict[str, Any] = field(default_factory=dict)

def create_media_source(value: Any) -> MediaSource:
    from .audio import PcmStreamResource, WavStreamResource, AudioStreamResource
    from .video import VideoStreamResource
    from .model_3d import Model3DStreamResource

    if isinstance(value, PcmStreamResource):
        return MediaSource(value, value.format, value.attrs)

    if isinstance(value, WavStreamResource):
        return MediaSource(value, "wav", value.attrs)

    if isinstance(value, AudioStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, VideoStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, Model3DStreamResource):
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
            return MediaSource(value)

    if isinstance(value, (bytes, bytearray)):
        return MediaSource(BytesStreamResource(bytes(value)))

    raise TypeError(f"Unsupported media source: {value.__class__.__name__}")
