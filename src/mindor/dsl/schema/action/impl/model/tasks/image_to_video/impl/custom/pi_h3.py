from typing import Union, Optional
from pydantic import Field
from ..common import CommonImageToVideoParamsConfig, CommonImageToVideoModelActionConfig

class PiH3ImageToVideoParamsConfig(CommonImageToVideoParamsConfig):
    video_shift: Optional[Union[float, str]] = Field(default=None, description="Flow-matching timestep shift applied to the video scheduler; overrides the adapter's default.")
    audio_shift: Optional[Union[float, str]] = Field(default=None, description="Flow-matching timestep shift applied to the audio scheduler; overrides the adapter's default.")

class PiH3ImageToVideoModelActionConfig(CommonImageToVideoModelActionConfig):
    params: PiH3ImageToVideoParamsConfig = Field(default_factory=PiH3ImageToVideoParamsConfig, description="pi-H3 image-to-video generation parameters.")
