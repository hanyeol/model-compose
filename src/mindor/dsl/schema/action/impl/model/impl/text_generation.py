from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

class TextGenerationParamsConfig(BaseModel):
    max_output_length: Union[int, str] = Field(default=1024, description="The maximum number of tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="The number of generated sequences to return.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; higher values produce more random results.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts to process in a single batch.")

class TextGenerationModelActionConfig(CommonModelInferenceActionConfig):
    prompt: Union[Union[str, List[str]], str] = Field(..., description="Input prompt to generate text from.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Text generation configuration parameters.")
