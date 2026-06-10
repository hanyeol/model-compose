from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from .streaming import StreamResource

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
