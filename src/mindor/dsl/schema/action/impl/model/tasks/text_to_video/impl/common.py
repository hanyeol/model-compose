from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonTextToVideoParamsConfig(BaseModel):
    num_frames: Union[int, str] = Field(default=81, description="Number of frames to generate.")

class CommonTextToVideoModelActionConfig(CommonModelActionConfig):
    prompt: Union[str, List[str]] = Field(..., description="Text description of the video to generate.")
    width: Union[int, str] = Field(default=1280, description="Output video width in pixels.")
    height: Union[int, str] = Field(default=720, description="Output video height in pixels.")
    frame_rate: Union[int, float, str] = Field(default=24, description="Output video frame rate; floats and NTSC rationals like 23.976 are accepted.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of prompts processed per batch.")
    params: CommonTextToVideoParamsConfig = Field(default_factory=CommonTextToVideoParamsConfig, description="Frame count parameters applied to generation.")
