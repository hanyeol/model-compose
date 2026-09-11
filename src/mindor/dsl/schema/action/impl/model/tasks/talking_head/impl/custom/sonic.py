from typing import Union, Optional
from pydantic import Field
from ..common import CommonTalkingHeadParamsConfig, CommonTalkingHeadModelActionConfig

class SonicTalkingHeadParamsConfig(CommonTalkingHeadParamsConfig):
    dynamic_scale: Union[float, str] = Field(default=1.0, description="Motion-dynamics scale; larger values produce more expressive head/facial motion.")
    inference_steps: Union[int, str] = Field(default=25, description="Number of diffusion inference steps.")
    min_resolution: Union[int, str] = Field(default=512, description="Minimum short-side resolution the face crop is resized to before rendering.")
    keep_resolution: Union[bool, str] = Field(default=False, description="Preserve the input portrait's original resolution instead of resizing to `min_resolution`.")

class SonicTalkingHeadModelActionConfig(CommonTalkingHeadModelActionConfig):
    params: SonicTalkingHeadParamsConfig = Field(default_factory=SonicTalkingHeadParamsConfig, description="Sonic generation parameters.")
