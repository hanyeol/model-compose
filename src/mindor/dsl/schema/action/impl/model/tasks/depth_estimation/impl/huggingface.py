from typing import Optional, Union
from pydantic import Field
from .common import CommonDepthEstimationModelActionConfig, CommonDepthEstimationParamsConfig

class HuggingfaceDepthEstimationParamsConfig(CommonDepthEstimationParamsConfig):
    input_size: Optional[Union[int, str]] = Field(default=None, description="Square model input resolution in pixels; images are resized to this size before inference. Defaults to the model's native size.")

class HuggingfaceDepthEstimationModelActionConfig(CommonDepthEstimationModelActionConfig):
    params: HuggingfaceDepthEstimationParamsConfig = Field(default_factory=HuggingfaceDepthEstimationParamsConfig)
