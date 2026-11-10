from typing import Union, Annotated
from pydantic import Field
from .hi_diff import HiDiffImageDeblurringModelComponentConfig
from .misc_filter import MiscFilterImageDeblurringModelComponentConfig

CustomImageDeblurringModelComponentConfig = Annotated[
    Union[
        HiDiffImageDeblurringModelComponentConfig,
        MiscFilterImageDeblurringModelComponentConfig,
    ],
    Field(discriminator="family")
]
