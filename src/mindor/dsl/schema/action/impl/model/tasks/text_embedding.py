from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextEmbeddingParamsConfig(BaseModel):
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="mean", description="Strategy used to aggregate token embeddings into a single vector.")
    normalize: Union[bool, str] = Field(default=True, description="Whether output embeddings are L2-normalized.")

class TextEmbeddingModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to embed.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per input text; unset uses the tokenizer's default.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts processed per batch.")
    params: TextEmbeddingParamsConfig = Field(default_factory=TextEmbeddingParamsConfig, description="Pooling and normalization parameters used to produce embeddings.")
