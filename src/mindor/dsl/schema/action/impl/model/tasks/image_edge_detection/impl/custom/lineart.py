from typing import Optional, Union
from pydantic import Field
from ..common import CommonImageEdgeDetectionModelActionConfig, CommonImageEdgeDetectionParamsConfig

class LineartImageEdgeDetectionParamsConfig(CommonImageEdgeDetectionParamsConfig):
    image_size: Optional[Union[int, str]] = Field(default=512, description="Square image resolution in pixels; images are resized to this size before being fed to the model.")

class LineartImageEdgeDetectionModelActionConfig(CommonImageEdgeDetectionModelActionConfig):
    params: LineartImageEdgeDetectionParamsConfig = Field(default_factory=LineartImageEdgeDetectionParamsConfig)
