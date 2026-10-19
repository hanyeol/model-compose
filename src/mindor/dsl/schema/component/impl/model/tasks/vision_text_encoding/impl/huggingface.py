from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VisionTextEncodingModelActionConfig
from .common import CommonVisionTextEncodingModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceVisionTextEncodingModelComponentConfig(CommonVisionTextEncodingModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    actions: List[VisionTextEncodingModelActionConfig] = Field(default_factory=list, description="Actions this vision-text encoding component exposes to workflows.")
