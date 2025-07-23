from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextEmbeddingParamsConfig(BaseModel):
    max_input_length: int = Field(default=512, description="Maximum number of tokens per input text.")
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="mean", description="Pooling strategy used to aggregate token embeddings.")
    normalize: bool = Field(default=True, description="Whether to apply L2 normalization to the output embeddings.")
    batch_size: int = Field(default=1, description="Number of input texts to process in a single batch.")

class TextEmbeddingModelActionConfig(CommonModelActionConfig):
    text: str = Field(..., description="Input text to be embedded.")
    params: TextEmbeddingParamsConfig = Field(default_factory=TextEmbeddingParamsConfig, description="Configuration parameters for embedding generation.")
