from typing import Union, Optional, List
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class VoiceEmbeddingParamsConfig(BaseModel):
    normalize: Union[bool, str] = Field(default=True, description="Whether output embeddings are L2-normalized.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Target sample rate applied to input audio before embedding; unset uses the model's native rate.")

class VoiceEmbeddingModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to embed, or a list of audios.")
    batch_size: Union[int, str] = Field(default=8, description="Number of audio inputs processed per batch.")
    params: VoiceEmbeddingParamsConfig = Field(default_factory=VoiceEmbeddingParamsConfig, description="Parameters controlling the produced embeddings.")
