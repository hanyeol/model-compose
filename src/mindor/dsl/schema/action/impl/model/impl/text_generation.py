from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextGenerationParamsConfig(BaseModel):
    max_output_length: int = Field(default=1024, description="The maximum number of tokens to generate.")
    num_return_sequences: int = Field(default=1, description="The number of generated sequences to return.")
    temperature: float = Field(default=1.0, description="Sampling temperature; higher values produce more random results.")
    top_k: int = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: float = Field(default=1.0, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")

class TextGenerationModelActionConfig(CommonModelActionConfig):
    prompt: str = Field(..., description="")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Text generation configuration parameters.")
