from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MiscFilterImageDeblurringModelActionConfig
from ..common import CommonImageDeblurringModelComponentConfig
from .common import ImageDeblurringModelFamily
from ....common import ModelDriverType

class MiscFilterImageDeblurringModelComponentConfig(CommonImageDeblurringModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageDeblurringModelFamily.MISC_FILTER]
    variant: Literal[ "RealBlur_J", "RealBlur_R", "GoPro" ] = Field(default="RealBlur_J", description="Training dataset of the MISCFilter checkpoint to load.")
    actions: List[MiscFilterImageDeblurringModelActionConfig] = Field(default_factory=list, description="Actions this image deblurring component exposes to workflows.")
