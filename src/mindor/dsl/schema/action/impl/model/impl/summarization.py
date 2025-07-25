from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class SummarizationParamsConfig(BaseModel):
    max_input_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens per input text.")
    max_output_length: Union[int, str] = Field(default=256, description="The maximum number of tokens to generate.")
    min_output_length: Union[int, str] = Field(default=30, description="The minimum number of tokens to generate.")
    num_beams: Union[int, str] = Field(default=4, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=2.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop the beam search when all beams finish generating.")
    do_sample: bool = Field(default=True, description="Whether to use sampling.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts to process in a single batch.")

class SummarizationModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text to summarize.")
    params: SummarizationParamsConfig = Field(default_factory=SummarizationParamsConfig, description="Summarization configuration parameters.")
