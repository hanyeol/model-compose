from typing import Literal
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTypedDecisionModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TYPED_DECISION]
