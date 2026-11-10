from typing import Optional, Union
from pydantic import Field
from ..common import CommonImageDeblurringModelActionConfig, CommonImageDeblurringParamsConfig

class MiscFilterImageDeblurringParamsConfig(CommonImageDeblurringParamsConfig):
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed forwarded to the augmentation shuffle; ignored when `augmented_inference` is False.")

class MiscFilterImageDeblurringModelActionConfig(CommonImageDeblurringModelActionConfig):
    params: MiscFilterImageDeblurringParamsConfig = Field(default_factory=MiscFilterImageDeblurringParamsConfig)
