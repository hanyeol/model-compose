from typing import Literal, List
from pydantic import Field, model_validator
from mindor.dsl.schema.action import HedImageEdgeDetectionModelActionConfig
from ..common import CommonImageEdgeDetectionModelComponentConfig
from .common import ImageEdgeDetectionModelFamily
from ....common import ModelDriverType, ModelProvider

_HED_WEIGHT_FILENAME = "ControlNetHED.pth"

class HedImageEdgeDetectionModelComponentConfig(CommonImageEdgeDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageEdgeDetectionModelFamily.HED]
    actions: List[HedImageEdgeDetectionModelActionConfig] = Field(default_factory=list, description="Actions this HED edge detection component exposes to workflows.")

    @model_validator(mode="after")
    def apply_default_filename(self):
        if self.model.provider == ModelProvider.HUGGINGFACE and self.model.filename is None:
            self.model.filename = _HED_WEIGHT_FILENAME
        return self
