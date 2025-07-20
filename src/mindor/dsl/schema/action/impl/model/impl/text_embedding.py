from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextEmbeddingParamsConfig(BaseModel):
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="mean", description="")
    normalize: bool = Field(default=True, description="")
    batch_size: int = Field(default=1, description="")
    max_length: int = Field(default=512, description="")
    device: str = Field(default="cpu", description="")

class TextEmbeddingModelActionConfig(CommonModelActionConfig):
    text: str = Field(..., description="")
    params: TextEmbeddingParamsConfig = Field(..., description="")
