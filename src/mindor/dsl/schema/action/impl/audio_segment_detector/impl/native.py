from typing import Union
from enum import Enum
from pydantic import Field
from .common import CommonAudioSegmentDetectorActionConfig

class NativeAudioSegmentDetectorStrategy(str, Enum):
    LAPLACIAN     = "laplacian"
    AGGLOMERATIVE = "agglomerative"

class NativeAudioSegmentDetectorActionConfig(CommonAudioSegmentDetectorActionConfig):
    strategy: Union[NativeAudioSegmentDetectorStrategy, str] = Field(default=NativeAudioSegmentDetectorStrategy.LAPLACIAN, description="Segmentation algorithm applied to derive boundaries.")
