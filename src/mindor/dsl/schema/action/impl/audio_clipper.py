from typing import Union, Optional, List
from pydantic import Field
from mindor.dsl.schema.common.media import MediaClipSpanConfig
from .common import CommonActionConfig

class AudioClipperActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to clip.")
    span: Union[MediaClipSpanConfig, List[MediaClipSpanConfig], str] = Field(..., description="Time span or spans to clip. A single object yields one clip; a list yields one per span.")
    merge: Union[bool, str] = Field(default=False, description="Whether to concatenate all clips into a single audio.")
    return_timestamp: Union[bool, str] = Field(default=False, description="Whether each clip carries its source span alongside the audio.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources processed per batch.")
