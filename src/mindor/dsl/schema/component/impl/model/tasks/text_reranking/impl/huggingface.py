from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextRerankingModelActionConfig
from .common import CommonTextRerankingModelComponentConfig
from ...common import ModelDriver

class HuggingfaceTextRerankingModelComponentConfig(CommonTextRerankingModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    actions: List[TextRerankingModelActionConfig] = Field(default_factory=list)
