from typing import Union, Optional
from pydantic import Field
from ..common import CommonTalkingHeadParamsConfig, CommonTalkingHeadModelActionConfig

class Hallo2TalkingHeadParamsConfig(CommonTalkingHeadParamsConfig):
    pose_weight: Union[float, str] = Field(default=1.1, description="Weight applied to the driving pose signal during motion module conditioning.")
    face_weight: Union[float, str] = Field(default=1.1, description="Weight applied to the driving face signal during motion module conditioning.")
    lip_weight: Union[float, str] = Field(default=1.1, description="Weight applied to the driving lip signal during motion module conditioning.")
    face_expand_ratio: Union[float, str] = Field(default=1.2, description="Face crop expansion ratio around the detected face box.")
    inference_steps: Union[int, str] = Field(default=40, description="Number of diffusion inference steps per denoising loop.")
    cfg_scale: Union[float, str] = Field(default=3.5, description="Classifier-free guidance scale.")
    motion_module_frames: Union[int, str] = Field(default=16, description="Number of frames processed per motion module window.")
    long_video: Union[bool, str] = Field(default=True, description="Enable Hallo2's long-video mode (chunk-and-blend) for audio longer than one window.")
    high_resolution: Union[bool, str] = Field(default=False, description="Run the built-in super-resolution pass to produce a higher-resolution output.")

class Hallo2TalkingHeadModelActionConfig(CommonTalkingHeadModelActionConfig):
    params: Hallo2TalkingHeadParamsConfig = Field(default_factory=Hallo2TalkingHeadParamsConfig, description="Hallo2 generation parameters.")
