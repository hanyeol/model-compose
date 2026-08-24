from typing import Union
from enum import Enum
from pydantic import Field
from .common import CommonAudioSegmentDetectorActionConfig

class AudioSegmentDetectorStrategy(str, Enum):
    LAPLACIAN     = "laplacian"
    AGGLOMERATIVE = "agglomerative"

class NativeAudioSegmentDetectorActionConfig(CommonAudioSegmentDetectorActionConfig):
    strategy: Union[AudioSegmentDetectorStrategy, str] = Field(default=AudioSegmentDetectorStrategy.LAPLACIAN, description="Segmentation algorithm applied to derive boundaries.")
