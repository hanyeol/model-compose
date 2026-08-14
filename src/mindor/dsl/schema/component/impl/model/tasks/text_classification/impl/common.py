from typing import Literal, Optional, List
from pydantic import Field
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextClassificationModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_CLASSIFICATION]
    labels: Optional[List[str]] = Field(default=None, description="Classification labels the model can output; overrides the model's built-in labels when set.")
