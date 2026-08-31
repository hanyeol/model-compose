from typing import Literal, Union
from pydantic import Field, model_validator
from ...common import CommonObjectTrackingModelActionConfig, CommonObjectTrackingParamsConfig

class YoloObjectTrackingParamsConfig(CommonObjectTrackingParamsConfig):
    tracker: Union[Literal[ "bytetrack", "botsort" ], str] = Field(default="bytetrack", description="Underlying Ultralytics tracker used for association.")

class YoloObjectTrackingModelActionConfig(CommonObjectTrackingModelActionConfig):
    params: YoloObjectTrackingParamsConfig = Field(default_factory=YoloObjectTrackingParamsConfig, description="YOLO-specific object tracking parameters.")

    @model_validator(mode="after")
    def validate_returns(self):
        return self
