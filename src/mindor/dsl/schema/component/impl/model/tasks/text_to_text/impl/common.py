from typing import Literal
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextToTextModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_TO_TEXT]
