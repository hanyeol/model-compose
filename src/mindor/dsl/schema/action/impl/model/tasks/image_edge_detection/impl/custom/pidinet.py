from typing import Optional, Union
from pydantic import Field
from ..common import CommonImageEdgeDetectionModelActionConfig, CommonImageEdgeDetectionParamsConfig

class PidinetImageEdgeDetectionParamsConfig(CommonImageEdgeDetectionParamsConfig):
    image_size: Optional[Union[int, str]] = Field(default=512, description="Square image resolution in pixels; images are resized to this size before being fed to the model.")
    use_safe_mode: Union[bool, str] = Field(default=False, description="Whether to apply the ControlNet 'safe' post-processing that suppresses low-confidence edges.")

class PidinetImageEdgeDetectionModelActionConfig(CommonImageEdgeDetectionModelActionConfig):
    params: PidinetImageEdgeDetectionParamsConfig = Field(default_factory=PidinetImageEdgeDetectionParamsConfig)
