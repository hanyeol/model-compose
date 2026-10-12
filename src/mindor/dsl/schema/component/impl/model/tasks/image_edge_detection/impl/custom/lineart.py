from typing import Literal, Union, List, Dict
from pydantic import Field, model_validator
from mindor.dsl.schema.action import LineartImageEdgeDetectionModelActionConfig
from mindor.dsl.schema.action.impl.model.tasks.image_edge_detection.impl.custom.common import LineartVariant
from ..common import CommonImageEdgeDetectionModelComponentConfig
from .common import ImageEdgeDetectionModelFamily
from ....common import ModelDriverType, ModelProvider

_LINEART_WEIGHT_FILENAMES: Dict[LineartVariant, str] = {
    LineartVariant.REALISTIC: "sk_model.pth",
    LineartVariant.COARSE:    "sk_model2.pth",
}

class LineartImageEdgeDetectionModelComponentConfig(CommonImageEdgeDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageEdgeDetectionModelFamily.LINEART]
    variant: Union[LineartVariant, str] = Field(default=LineartVariant.REALISTIC, description="Lineart model variant; 'realistic' is the detailed sk_model, 'coarse' is the simpler sk_model2.")
    actions: List[LineartImageEdgeDetectionModelActionConfig] = Field(default_factory=list, description="Actions this Lineart edge detection component exposes to workflows.")

    @model_validator(mode="after")
    def apply_default_filename(self):
        if self.model.provider == ModelProvider.HUGGINGFACE and self.model.filename is None:
            self.model.filename = _LINEART_WEIGHT_FILENAMES[self.variant]
        return self
