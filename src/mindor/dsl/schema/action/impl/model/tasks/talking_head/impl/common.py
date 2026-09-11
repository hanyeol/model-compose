from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonTalkingHeadParamsConfig(BaseModel):
    fps: Union[int, str] = Field(default=25, description="Output video frame rate.")

class CommonTalkingHeadModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input portrait image or list of images used as the source face.")
    audio: Union[str, List[str]] = Field(..., description="Input audio or list of audios driving the lip sync.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonTalkingHeadParamsConfig = Field(default_factory=CommonTalkingHeadParamsConfig, description="Generation parameters applied to the talking head video.")
