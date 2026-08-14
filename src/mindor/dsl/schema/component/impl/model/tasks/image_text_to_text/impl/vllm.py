from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from .common import CommonImageTextToTextModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmImageTextToTextModelComponentConfig(CommonImageTextToTextModelComponentConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    options: Optional[VllmEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to vLLM when loading the model.")
    actions: List[ImageTextToTextModelActionConfig] = Field(default_factory=list, description="Actions this image-text-to-text component exposes to workflows.")
