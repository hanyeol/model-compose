from typing import Union, List, Any
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class VideoEmbeddingParamsConfig(BaseModel):
    normalize: Union[bool, str] = Field(default=True, description="Whether output embeddings are L2-normalized.")

class VideoEmbeddingModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to embed; a single video's frames, a list of frames, a list of per-video frame batches, or a stream of batches.")
    batch_size: Union[int, str] = Field(default=1, description="Number of videos processed per batch.")
    params: VideoEmbeddingParamsConfig = Field(default_factory=VideoEmbeddingParamsConfig, description="Normalization parameters used to produce embeddings.")
