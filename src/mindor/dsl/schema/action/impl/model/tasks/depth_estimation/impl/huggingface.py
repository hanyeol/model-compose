from typing import Optional, Union
from pydantic import Field
from .common import CommonDepthEstimationModelActionConfig, CommonDepthEstimationParamsConfig

class HuggingfaceDepthEstimationParamsConfig(CommonDepthEstimationParamsConfig):
    image_size: Optional[Union[int, str]] = Field(default=None, description="Square image resolution in pixels; images are resized to this size before being fed to the model. Defaults to the model's native size.")

class HuggingfaceDepthEstimationModelActionConfig(CommonDepthEstimationModelActionConfig):
    params: HuggingfaceDepthEstimationParamsConfig = Field(default_factory=HuggingfaceDepthEstimationParamsConfig)
