from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextClassificationModelTrainerActionConfig
from .common import CommonTextClassificationModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class HuggingfaceTextClassificationModelTrainerComponentConfig(CommonTextClassificationModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.HUGGINGFACE]
    actions: List[TextClassificationModelTrainerActionConfig] = Field(default_factory=list, description="Actions this text-classification trainer component exposes to workflows.")
