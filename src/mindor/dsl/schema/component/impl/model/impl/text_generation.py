from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelComponentConfig, ModelTaskType

class TextGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_GENERATION]
