from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioFeatureExtractorDriver(str, Enum):
    NATIVE = "native"
    FFMPEG = "ffmpeg"

class CommonAudioFeatureExtractorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_FEATURE_EXTRACTOR]
    driver: AudioFeatureExtractorDriver = Field(..., description="Backend implementation used for audio feature extraction.")
