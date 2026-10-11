from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import DepthEstimationModelActionConfig
from .common import CommonDepthEstimationModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceDepthEstimationModelArchitecture(str, Enum):
    AUTO           = "auto"
    DPT            = "dpt"
    DEPTH_ANYTHING = "depth-anything"

class HuggingfaceDepthEstimationModelComponentConfig(CommonDepthEstimationModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceDepthEstimationModelArchitecture = Field(default=HuggingfaceDepthEstimationModelArchitecture.AUTO, description="Model architecture family; \"auto\" infers from the model config.")
    actions: List[DepthEstimationModelActionConfig] = Field(default_factory=list, description="Actions this depth estimation component exposes to workflows.")
