from typing import Union, List, Optional
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class MusicSourceSeparationParamsConfig(BaseModel):
    stems: Union[List[str], str] = Field(default_factory=lambda: [ "vocals" ], description="Stems to return (e.g. ['vocals'], ['vocals','drums','bass','other']). Available stems depend on the model.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Sample rate of the returned stem audio. Defaults to the model's native rate (Demucs: 44100, MDX-Net: 44100).")
    overlap: Optional[Union[float, str]] = Field(default=None, description="Overlap ratio between chunks during separation (0.0-0.99). Higher values improve quality at the cost of speed.")
    shifts: Optional[Union[int, str]] = Field(default=None, description="Number of random shifts for equivariant stabilization. Higher = better quality but slower (Demucs only).")

class MusicSourceSeparationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    params: MusicSourceSeparationParamsConfig = Field(default_factory=MusicSourceSeparationParamsConfig, description="Music source separation parameters.")
