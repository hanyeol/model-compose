from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextEncodingModelActionConfig
from .common import CommonTextEncodingModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceTextEncodingModelComponentConfig(CommonTextEncodingModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    actions: List[TextEncodingModelActionConfig] = Field(default_factory=list, description="Actions this text encoding component exposes to workflows.")
