from dataclasses import dataclass
from typing import Optional

@dataclass
class VideoEncoderParams:
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    resolution: Optional[str] = None
    fps: Optional[float] = None

@dataclass
class AudioEncoderParams:
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None

@dataclass
class VideoAudioEncodingParams:
    """Rendered encoding parameters ready for the driver / session / recorder layer.

    Values here are already resolved from variable references (${input.foo})
    and normalized (e.g. bitrate parsed to bits per second), so downstream
    consumers don't need to touch the DSL config again.
    """
    format: Optional[str] = None
    video: Optional[VideoEncoderParams] = None
    audio: Optional[AudioEncoderParams] = None
