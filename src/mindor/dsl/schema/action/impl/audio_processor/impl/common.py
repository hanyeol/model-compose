from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioProcessorActionMethod(str, Enum):
    HIGHPASS     = "highpass"
    LOWPASS      = "lowpass"
    PITCH_SHIFT  = "pitch-shift"
    DC_SHIFT     = "dc-shift"
    COMPRESSOR   = "compressor"
    GAIN         = "gain"
    CHORUS       = "chorus"
    DELAY        = "delay"
    REVERB       = "reverb"
    NORMALIZE    = "normalize"
    PEAK_LIMIT   = "peak-limit"
    TRIM_EDGES   = "trim-edges"
    TRIM_SILENCE = "trim-silence"

class CommonAudioProcessorActionConfig(CommonActionConfig):
    method: AudioProcessorActionMethod = Field(..., description="Audio processor method.")
    audio: Union[str, List[str]] = Field(..., description="Input audio(s) (file path, bytes, or variable reference).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios per batch.")
