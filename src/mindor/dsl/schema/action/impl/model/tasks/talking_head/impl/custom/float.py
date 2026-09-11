from typing import Union, Optional
from pydantic import Field
from ..common import CommonTalkingHeadParamsConfig, CommonTalkingHeadModelActionConfig

class FloatTalkingHeadParamsConfig(CommonTalkingHeadParamsConfig):
    emotion: Optional[Union[str]] = Field(default=None, description="Optional emotion label conditioning the output (e.g. 'happy', 'sad', 'angry').")
    emotion_scale: Union[float, str] = Field(default=1.0, description="Multiplier applied to the emotion conditioning strength.")
    inference_steps: Union[int, str] = Field(default=10, description="Number of flow-matching inference steps.")
    cfg_scale: Union[float, str] = Field(default=2.0, description="Classifier-free guidance scale.")
    a_cfg_scale: Union[float, str] = Field(default=2.0, description="Guidance scale applied to the audio conditioning branch.")
    e_cfg_scale: Union[float, str] = Field(default=1.0, description="Guidance scale applied to the emotion conditioning branch.")
    crop: Union[bool, str] = Field(default=True, description="Crop the source portrait to the detected face before rendering; disable to render the full frame.")

class FloatTalkingHeadModelActionConfig(CommonTalkingHeadModelActionConfig):
    params: FloatTalkingHeadParamsConfig = Field(default_factory=FloatTalkingHeadParamsConfig, description="Float generation parameters.")
