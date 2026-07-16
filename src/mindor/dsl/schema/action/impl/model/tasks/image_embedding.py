from typing import Union, Literal, Optional, List
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class ImageEmbeddingParamsConfig(BaseModel):
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="cls", description="Pooling strategy for aggregating patch embeddings (ignored by architectures with a built-in pooler like CLIP/SigLIP).")
    normalize: Union[bool, str] = Field(default=True, description="Whether to L2-normalize output embeddings.")

class ImageEmbeddingModelActionConfig(CommonModelActionConfig):
    image: Union[Union[str, List[str]], str] = Field(..., description="Input image (path, URL, or base64) to embed.")
    batch_size: Union[int, str] = Field(default=8, description="Input images per batch.")
    params: ImageEmbeddingParamsConfig = Field(default_factory=ImageEmbeddingParamsConfig, description="Embedding generation parameters.")
