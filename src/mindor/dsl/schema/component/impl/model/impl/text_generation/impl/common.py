from typing import Literal
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextGenerationModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_GENERATION]
