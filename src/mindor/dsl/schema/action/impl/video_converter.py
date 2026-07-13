from typing import Union, Optional, List
from pydantic import Field
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class VideoConverterActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source(s).")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Video/audio encoding settings.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos per batch.")
