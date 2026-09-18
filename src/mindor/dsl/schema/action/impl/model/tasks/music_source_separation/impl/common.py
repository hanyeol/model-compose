from enum import Enum
from typing import Union, List, Optional
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class MusicSourceSeparationStem(str, Enum):
    VOCALS        = "vocals"
    DRUMS         = "drums"
    BASS          = "bass"
    OTHER         = "other"
    GUITAR        = "guitar"
    PIANO         = "piano"
    INSTRUMENTAL  = "instrumental"
    ACCOMPANIMENT = "accompaniment"

class CommonMusicSourceSeparationParamsConfig(BaseModel):
    stems: Optional[Union[List[Union[MusicSourceSeparationStem, str]], str]] = Field(default=None, description="Stems returned in the result; when omitted, every stem the model produces is returned.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Sample rate in Hz of the returned stems; defaults to the model's native rate.")
    overlap: Optional[Union[float, str]] = Field(default=None, description="Overlap ratio between chunks during separation, from 0.0 to 0.99; higher values improve quality at the cost of speed.")

class CommonMusicSourceSeparationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to separate, or a list of audios.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    params: CommonMusicSourceSeparationParamsConfig = Field(default_factory=CommonMusicSourceSeparationParamsConfig, description="Stem selection and separation quality parameters.")
