from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

class TextEmbeddingParamsConfig(BaseModel):
    max_input_length: Union[int, str] = Field(default=512, description="Maximum number of tokens per input text.")
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="mean", description="Pooling strategy used to aggregate token embeddings.")
    normalize: Union[bool, str] = Field(default=True, description="Whether to apply L2 normalization to the output embeddings.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts to process in a single batch.")

class TextEmbeddingModelActionConfig(CommonModelInferenceActionConfig):
    text: Union[Union[str, List[str]], str] = Field(..., description="Input text to be embedded.")
    params: TextEmbeddingParamsConfig = Field(default_factory=TextEmbeddingParamsConfig, description="Configuration parameters for embedding generation.")
