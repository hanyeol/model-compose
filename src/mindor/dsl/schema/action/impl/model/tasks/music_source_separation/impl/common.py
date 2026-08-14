from typing import Union, List, Optional
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class MusicSourceSeparationParamsConfig(BaseModel):
    stems: Union[List[str], str] = Field(default_factory=lambda: [ "vocals" ], description="Stems returned in the result; available stems depend on the model (e.g., vocals, drums, bass, other).")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Sample rate in Hz of the returned stems; defaults to the model's native rate.")
    overlap: Optional[Union[float, str]] = Field(default=None, description="Overlap ratio between chunks during separation, from 0.0 to 0.99; higher values improve quality at the cost of speed.")
    shifts: Optional[Union[int, str]] = Field(default=None, description="Number of random shifts for equivariant stabilization; higher values improve quality but are slower (Demucs only).")

class MusicSourceSeparationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio path, URL, or list of audio inputs to separate.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    params: MusicSourceSeparationParamsConfig = Field(default_factory=MusicSourceSeparationParamsConfig, description="Stem selection and separation quality parameters.")
