from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextGenerationParamsConfig(BaseModel):
    max_length: int = Field(default=128, description="")
    num_return_sequences: int = Field(default=1, description="")
    temperature: float = Field(default=1.0, description="")
    top_k: int = Field(default=50, description="")
    top_p: float = Field(default=1.0, description="")

class TextGenerationModelActionConfig(CommonModelActionConfig):
    prompt: str = Field(..., description="")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Text generation configuration parameters.")
