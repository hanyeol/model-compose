from typing import Union
from enum import Enum
from pydantic import Field
from .common import CommonMusicSegmentDetectorActionConfig

class NativeMusicSegmentDetectorStrategy(str, Enum):
    LAPLACIAN     = "laplacian"
    AGGLOMERATIVE = "agglomerative"

class NativeMusicSegmentDetectorActionConfig(CommonMusicSegmentDetectorActionConfig):
    strategy: Union[NativeMusicSegmentDetectorStrategy, str] = Field(default=NativeMusicSegmentDetectorStrategy.LAPLACIAN, description="Segmentation algorithm applied to derive boundaries.")
