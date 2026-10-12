from typing import Literal, List
from pydantic import Field, model_validator
from mindor.dsl.schema.action import PidinetImageEdgeDetectionModelActionConfig
from ..common import CommonImageEdgeDetectionModelComponentConfig
from .common import ImageEdgeDetectionModelFamily
from ....common import ModelDriverType, ModelProvider

_PIDINET_WEIGHT_FILENAME = "table5_pidinet.pth"

class PidinetImageEdgeDetectionModelComponentConfig(CommonImageEdgeDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageEdgeDetectionModelFamily.PIDINET]
    actions: List[PidinetImageEdgeDetectionModelActionConfig] = Field(default_factory=list, description="Actions this PiDiNet edge detection component exposes to workflows.")

    @model_validator(mode="after")
    def apply_default_filename(self):
        if self.model.provider == ModelProvider.HUGGINGFACE and self.model.filename is None:
            self.model.filename = _PIDINET_WEIGHT_FILENAME
        return self
