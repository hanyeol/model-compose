from typing import Union
from pydantic import Field
from .common import CommonImageBackgroundRemovalModelActionConfig, CommonImageBackgroundRemovalParamsConfig

class HuggingfaceImageBackgroundRemovalParamsConfig(CommonImageBackgroundRemovalParamsConfig):
    image_size: Union[int, str] = Field(default=1024, description="Square image resolution in pixels; images are resized to this size before being fed to the model.")

class HuggingfaceImageBackgroundRemovalModelActionConfig(CommonImageBackgroundRemovalModelActionConfig):
    params: HuggingfaceImageBackgroundRemovalParamsConfig = Field(default_factory=HuggingfaceImageBackgroundRemovalParamsConfig)
