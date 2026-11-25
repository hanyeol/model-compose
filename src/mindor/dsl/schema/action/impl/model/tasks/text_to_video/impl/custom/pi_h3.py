from typing import Union, Optional
from pydantic import Field
from ..common import CommonTextToVideoParamsConfig, CommonTextToVideoModelActionConfig

class PiH3TextToVideoParamsConfig(CommonTextToVideoParamsConfig):
    video_shift: Optional[Union[float, str]] = Field(default=None, description="Flow-matching timestep shift applied to the video scheduler; overrides the adapter's default.")
    audio_shift: Optional[Union[float, str]] = Field(default=None, description="Flow-matching timestep shift applied to the audio scheduler; overrides the adapter's default.")

class PiH3TextToVideoModelActionConfig(CommonTextToVideoModelActionConfig):
    params: PiH3TextToVideoParamsConfig = Field(default_factory=PiH3TextToVideoParamsConfig, description="pi-H3 text-to-video generation parameters.")
