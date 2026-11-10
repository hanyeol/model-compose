from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HiDiffImageDeblurringModelActionConfig
from ..common import CommonImageDeblurringModelComponentConfig
from .common import ImageDeblurringModelFamily
from ....common import ModelDriverType

class HiDiffVariant(str):
    pass

class HiDiffImageDeblurringModelComponentConfig(CommonImageDeblurringModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageDeblurringModelFamily.HI_DIFF]
    variant: Literal[ "RealBlur_J", "RealBlur_R", "GoPro" ] = Field(default="RealBlur_J", description="Training dataset of the HI-Diff checkpoint to load.")
    actions: List[HiDiffImageDeblurringModelActionConfig] = Field(default_factory=list, description="Actions this image deblurring component exposes to workflows.")
