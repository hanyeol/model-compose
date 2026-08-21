from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioMetric(str, Enum):
    LOUDNESS = "loudness"
    PEAK     = "peak"
    GAIN     = "gain"
    CLIPPING = "clipping"
    SILENCE  = "silence"

class CommonAudioAnalyzerActionConfig(CommonActionConfig):
    metric: AudioMetric = Field(..., description="Kind of measurement performed on the audio.")
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to analyze.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")
