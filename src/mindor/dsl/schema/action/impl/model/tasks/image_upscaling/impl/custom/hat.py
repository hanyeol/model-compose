from typing import Union
from pydantic import Field
from ..common import CommonImageUpscalingModelActionConfig, CommonImageUpscalingParamsConfig

class HatImageUpscalingParamsConfig(CommonImageUpscalingParamsConfig):
    tile_pad_size: Union[int, str] = Field(default=24, description="Padding in pixels added around each tile to avoid seam artifacts.")

class HatImageUpscalingModelActionConfig(CommonImageUpscalingModelActionConfig):
    params: HatImageUpscalingParamsConfig = Field(default_factory=HatImageUpscalingParamsConfig)
