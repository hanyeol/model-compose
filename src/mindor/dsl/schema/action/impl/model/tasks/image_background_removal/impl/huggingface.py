from typing import Union
from pydantic import Field
from .common import CommonImageBackgroundRemovalModelActionConfig, CommonImageBackgroundRemovalParamsConfig

class HuggingfaceImageBackgroundRemovalParamsConfig(CommonImageBackgroundRemovalParamsConfig):
    input_size: Union[int, str] = Field(default=1024, description="Square model input resolution in pixels; images are resized to this size before inference.")

class HuggingfaceImageBackgroundRemovalModelActionConfig(CommonImageBackgroundRemovalModelActionConfig):
    params: HuggingfaceImageBackgroundRemovalParamsConfig = Field(default_factory=HuggingfaceImageBackgroundRemovalParamsConfig)
