from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonMusicSegmentDetectorActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to segment.")
    min_segment_duration: Union[float, int, str] = Field(default="2s", description="Minimum duration of a segment; shorter segments are merged into a neighbor.")
    sample_rate: Union[int, str] = Field(default=22050, description="Target mono PCM sample rate used for analysis.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")
