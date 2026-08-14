from typing import Union, Optional, List
from pydantic import Field
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class VideoConverterActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to convert.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the output video and audio.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")
