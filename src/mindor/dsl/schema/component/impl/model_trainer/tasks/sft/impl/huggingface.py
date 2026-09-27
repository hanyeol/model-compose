from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SftModelTrainerActionConfig
from .common import CommonSftModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class HuggingfaceSftModelTrainerComponentConfig(CommonSftModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.HUGGINGFACE]
    actions: List[SftModelTrainerActionConfig] = Field(default_factory=list, description="Actions this SFT trainer component exposes to workflows.")
