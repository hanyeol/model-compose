from typing import Literal, Union, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import TransNetV2ShotBoundaryDetectionModelActionConfig
from ..common import CommonShotBoundaryDetectionModelComponentConfig
from .common import ShotBoundaryDetectionModelFamily
from ....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

class TransNetV2ShotBoundaryDetectionLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "transnetv2"

TransNetV2ShotBoundaryDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        TransNetV2ShotBoundaryDetectionLocalModelConfig,
    ],
    Field(discriminator="provider")
]

class TransNetV2ShotBoundaryDetectionModelComponentConfig(CommonShotBoundaryDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ShotBoundaryDetectionModelFamily.TRANSNETV2]
    model: TransNetV2ShotBoundaryDetectionModelConfig = Field(..., description="TransNetV2 model directory — a local path to the SavedModel folder containing saved_model.pb and variables/.")
    actions: List[TransNetV2ShotBoundaryDetectionModelActionConfig] = Field(default_factory=list, description="Actions this shot boundary detection component exposes to workflows.")
