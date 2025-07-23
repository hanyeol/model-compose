from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class SummarizationParamsConfig(BaseModel):
    max_input_length: int = Field(default=1024, description="Maximum number of tokens per input text.")
    max_output_length: int = Field(default=256, description="The maximum number of tokens to generate.")
    min_output_length: int = Field(default=30, description="The minimum number of tokens to generate.")
    num_beams: int = Field(default=4, description="")
    length_penalty: float = Field(default=2.0, description="")
    early_stopping: bool = Field(default=True, description="")
    do_sample: bool = Field(default=True, description="Whether to use sampling.")

class SummarizationModelActionConfig(CommonModelActionConfig):
    text: str = Field(..., description="")
    params: SummarizationParamsConfig = Field(default_factory=SummarizationParamsConfig, description="Summarization configuration parameters.")
