from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextGenerationParamsConfig(BaseModel):
    max_output_length: int = Field(default=1024, description="Maximum number of tokens to generate.")
    temperature: float = Field(default=0.7, description="Sampling temperature; higher values yield more random outputs.")
    top_p: float = Field(default=0.9, description="Nucleus sampling: include tokens with cumulative probability up to top_p.")

class TextGenerationModelActionConfig(CommonModelActionConfig):
    prompt: Union[str, List[str]] = Field(..., description="Input prompt to generate text from.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Text generation configuration parameters.")
