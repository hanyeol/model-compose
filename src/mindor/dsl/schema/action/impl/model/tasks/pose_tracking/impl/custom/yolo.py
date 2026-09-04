from typing import Literal, Union
from pydantic import Field, model_validator
from ..common import CommonPoseTrackingModelActionConfig, CommonPoseTrackingParamsConfig

class YoloPoseTrackingParamsConfig(CommonPoseTrackingParamsConfig):
    tracker: Union[Literal[ "bytetrack", "botsort" ], str] = Field(default="bytetrack", description="Underlying Ultralytics tracker used for association.")

class YoloPoseTrackingModelActionConfig(CommonPoseTrackingModelActionConfig):
    params: YoloPoseTrackingParamsConfig = Field(default_factory=YoloPoseTrackingParamsConfig, description="YOLO-specific pose tracking parameters.")

    @model_validator(mode="after")
    def validate_returns(self):
        return self
