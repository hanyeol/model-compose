from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextEmbeddingParamsConfig(BaseModel):
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="mean", description="Pooling strategy for aggregating token embeddings.")
    normalize: Union[bool, str] = Field(default=True, description="Whether to L2-normalize output embeddings.")

class TextEmbeddingModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text to embed.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens per input text. None uses the tokenizer's model_max_length.")
    batch_size: Union[int, str] = Field(default=32, description="Input texts per batch.")
    params: TextEmbeddingParamsConfig = Field(default_factory=TextEmbeddingParamsConfig, description="Embedding generation parameters.")
