from typing import Union, List
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class MusicEmbeddingParamsConfig(BaseModel):
    normalize: Union[bool, str] = Field(default=True, description="Whether output embeddings are L2-normalized.")

class MusicEmbeddingModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to embed, or a list of audios.")
    batch_size: Union[int, str] = Field(default=8, description="Number of audio inputs processed per batch.")
    params: MusicEmbeddingParamsConfig = Field(default_factory=MusicEmbeddingParamsConfig, description="Parameters controlling the produced embeddings.")
