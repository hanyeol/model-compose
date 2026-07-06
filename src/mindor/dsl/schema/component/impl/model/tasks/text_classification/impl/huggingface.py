from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from .common import CommonTextClassificationModelComponentConfig
from ...common import ModelDriver

class HuggingfaceTextClassificationModelComponentConfig(CommonTextClassificationModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    actions: List[TextClassificationModelActionConfig] = Field(default_factory=list)
