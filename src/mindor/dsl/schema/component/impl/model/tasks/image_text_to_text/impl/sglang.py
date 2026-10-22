from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from .common import CommonImageTextToTextModelComponentConfig
from ...common import ModelDriverType
from ...base.sglang import SglangEngineOptionsConfig

class SglangImageTextToTextModelComponentConfig(CommonImageTextToTextModelComponentConfig):
    driver: Literal[ModelDriverType.SGLANG] = Field(default=ModelDriverType.SGLANG)
    options: Optional[SglangEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to SGLang when loading the model.")
    actions: List[ImageTextToTextModelActionConfig] = Field(default_factory=list, description="Actions this image-text-to-text component exposes to workflows.")
