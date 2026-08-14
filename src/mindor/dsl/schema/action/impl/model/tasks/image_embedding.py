from typing import Union, Literal, Optional, List
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class ImageEmbeddingParamsConfig(BaseModel):
    pooling: Literal[ "mean", "cls", "max" ] = Field(default="cls", description="Strategy used to aggregate patch embeddings; ignored by architectures with a built-in pooler such as CLIP or SigLIP.")
    normalize: Union[bool, str] = Field(default=True, description="Whether output embeddings are L2-normalized.")

class ImageEmbeddingModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images (path, URL, or base64) to embed.")
    batch_size: Union[int, str] = Field(default=8, description="Number of input images processed per batch.")
    params: ImageEmbeddingParamsConfig = Field(default_factory=ImageEmbeddingParamsConfig, description="Pooling and normalization parameters used to produce embeddings.")
