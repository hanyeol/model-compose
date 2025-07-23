from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TranslationParamsConfig(BaseModel):
    max_input_length: int = Field(default=1024, description="Maximum number of tokens per input text.")
    max_output_length: int = Field(default=256, description="The maximum number of tokens to generate.")
    min_output_length: int = Field(default=10, description="The minimum number of tokens to generate.")
    num_beams: int = Field(default=4, description="")
    length_penalty: float = Field(default=1.0, description="")

class TranslationModelActionConfig(CommonModelActionConfig):
    text: str = Field(..., description="")
    params: TranslationParamsConfig = Field(default_factory=TranslationParamsConfig, description="Translation configuration parameters.")
