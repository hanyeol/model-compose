from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextGenerationParamsConfig(BaseModel):
    pass

class TextGenerationModelActionConfig(CommonModelActionConfig):
    prompt: str = Field(..., description="")
    params: TextGenerationParamsConfig = Field(..., description="")
