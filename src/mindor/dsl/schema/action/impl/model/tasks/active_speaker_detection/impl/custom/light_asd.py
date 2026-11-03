from typing import Union
from pydantic import Field
from ..common import CommonActiveSpeakerDetectionParamsConfig, CommonActiveSpeakerDetectionModelActionConfig

class LightAsdActiveSpeakerDetectionParamsConfig(CommonActiveSpeakerDetectionParamsConfig):
    face_crop_scale: Union[float, str] = Field(default=0.4, description="Columbia-style face crop scale; each side extends by this ratio of max(w,h)/2, bottom extends by twice as much to include the mouth")

class LightAsdActiveSpeakerDetectionModelActionConfig(CommonActiveSpeakerDetectionModelActionConfig):
    params: LightAsdActiveSpeakerDetectionParamsConfig = Field(default_factory=LightAsdActiveSpeakerDetectionParamsConfig, description="Light-ASD scoring parameters.")
