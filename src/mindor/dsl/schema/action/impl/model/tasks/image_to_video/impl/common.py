from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonImageToVideoParamsConfig(BaseModel):
    num_frames: Union[int, str] = Field(default=81, description="Number of frames to generate.")
    fps: Union[int, str] = Field(default=24, description="Output video frame rate.")
    height: Optional[Union[int, str]] = Field(default=None, description="Output video height; defaults to the input image height when unset.")
    width: Optional[Union[int, str]] = Field(default=None, description="Output video width; defaults to the input image width when unset.")

class CommonImageToVideoModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images used as the first frame.")
    prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text prompt guiding motion and content of the generated video.")
    negative_prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text describing content to avoid in the generated video.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonImageToVideoParamsConfig = Field(default_factory=CommonImageToVideoParamsConfig, description="Frame count, resolution, and fps parameters applied to generation.")
