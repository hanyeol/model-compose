from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

class SummarizationParamsConfig(BaseModel):
    max_input_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens per input text.")
    max_output_length: Union[int, str] = Field(default=256, description="Maximum number of tokens to generate.")
    min_output_length: Union[int, str] = Field(default=30, description="Minimum number of tokens to generate.")
    num_beams: Union[int, str] = Field(default=4, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=2.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop the beam search when all beams finish generating.")
    do_sample: bool = Field(default=True, description="Whether to use sampling to generate diverse summaries.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=1.0, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts to process in a single batch.")

class SummarizationModelActionConfig(CommonModelInferenceActionConfig):
    text: Union[Union[str, List[str]], str] = Field(..., description="Input text to summarize.")
    params: SummarizationParamsConfig = Field(default_factory=SummarizationParamsConfig, description="Summarization configuration parameters.")
