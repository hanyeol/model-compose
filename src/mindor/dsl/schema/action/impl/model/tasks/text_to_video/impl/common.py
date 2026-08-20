from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonTextToVideoParamsConfig(BaseModel):
    num_frames: Union[int, str] = Field(default=81, description="Number of frames to generate.")
    fps: Union[int, str] = Field(default=24, description="Output video frame rate.")
    height: Union[int, str] = Field(default=720, description="Output video height in pixels.")
    width: Union[int, str] = Field(default=1280, description="Output video width in pixels.")

class CommonTextToVideoModelActionConfig(CommonModelActionConfig):
    prompt: Union[str, List[str]] = Field(..., description="Text description of the video to generate.")
    negative_prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text describing content to avoid in the generated video.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of prompts processed per batch.")
    params: CommonTextToVideoParamsConfig = Field(default_factory=CommonTextToVideoParamsConfig, description="Frame count, resolution, and fps parameters applied to generation.")
