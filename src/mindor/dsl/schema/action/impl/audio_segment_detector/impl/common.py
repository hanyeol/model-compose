from typing import Union, Literal, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioSegmentDetectorStrategy(str, Enum):
    LAPLACIAN     = "laplacian"
    AGGLOMERATIVE = "agglomerative"

class CommonAudioSegmentDetectorActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to segment.")
    strategy: Union[AudioSegmentDetectorStrategy, str] = Field(default=AudioSegmentDetectorStrategy.LAPLACIAN, description="Segmentation algorithm applied to derive boundaries.")
    return_labels: Union[bool, str] = Field(default=True, description="Whether structural cluster labels are included with each segment.")
    min_segment_duration: Union[float, int, str] = Field(default="4s", description="Minimum duration of a segment; shorter segments are merged into a neighbor.")
    sample_rate: Union[int, str] = Field(default=22050, description="Target mono PCM sample rate used for analysis.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")
