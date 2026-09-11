from typing import Union, Optional, List
from pydantic import Field
from ..common import CommonTalkingHeadParamsConfig, CommonTalkingHeadModelActionConfig

class Hallo3TalkingHeadParamsConfig(CommonTalkingHeadParamsConfig):
    prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Optional text prompt guiding scene, style, or motion.")
    negative_prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text describing content to avoid.")
    inference_steps: Union[int, str] = Field(default=50, description="Number of DiT inference steps.")
    guidance_scale: Union[float, str] = Field(default=6.0, description="Classifier-free guidance scale for text conditioning.")
    audio_guidance_scale: Union[float, str] = Field(default=3.0, description="Guidance scale applied to the audio conditioning branch.")
    resolution: Union[int, str] = Field(default=480, description="Output frame resolution (short-side length in pixels).")
    num_frames: Union[int, str] = Field(default=97, description="Number of frames generated per DiT window.")
    shift: Union[float, str] = Field(default=5.0, description="Flow-matching timestep shift applied to the scheduler.")
    long_video: Union[bool, str] = Field(default=True, description="Enable long-video mode (window-and-blend) for audio longer than one DiT window.")

class Hallo3TalkingHeadModelActionConfig(CommonTalkingHeadModelActionConfig):
    params: Hallo3TalkingHeadParamsConfig = Field(default_factory=Hallo3TalkingHeadParamsConfig, description="Hallo3 generation parameters.")
