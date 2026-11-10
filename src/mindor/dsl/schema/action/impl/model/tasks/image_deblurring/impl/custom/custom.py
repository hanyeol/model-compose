from typing import Union
from .hi_diff import HiDiffImageDeblurringModelActionConfig
from .misc_filter import MiscFilterImageDeblurringModelActionConfig

CustomImageDeblurringModelActionConfig = Union[
    HiDiffImageDeblurringModelActionConfig,
    MiscFilterImageDeblurringModelActionConfig,
]
