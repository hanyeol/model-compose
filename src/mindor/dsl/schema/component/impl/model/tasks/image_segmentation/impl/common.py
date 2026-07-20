from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageSegmentationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_SEGMENTATION]
