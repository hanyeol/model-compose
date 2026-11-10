from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageDeblurringModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_DEBLURRING]
