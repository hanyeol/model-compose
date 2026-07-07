from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioFeature(str, Enum):
    SPECTRUM = "spectrum"
    WAVEFORM = "waveform"

class CommonAudioFeatureExtractorActionConfig(CommonActionConfig):
    feature: AudioFeature = Field(..., description="Type of feature to extract from the audio.")
    audio: Union[str, List[str]] = Field(..., description="Audio source(s).")
    fps: Union[int, str] = Field(default=30, description="Output frames per second.")
    sample_rate: Union[int, str] = Field(default=22050, description="Sample rate used for internal PCM decoding (mono).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios to process in a single batch.")
