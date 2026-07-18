from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioProcessorActionMethod(str, Enum):
    RESAMPLE     = "resample"
    HIGHPASS     = "highpass"
    LOWPASS      = "lowpass"
    BELL         = "bell"
    LOW_SHELF    = "low-shelf"
    HIGH_SHELF   = "high-shelf"
    PITCH_SHIFT  = "pitch-shift"
    DC_SHIFT     = "dc-shift"
    COMPRESSOR   = "compressor"
    NOISE_GATE   = "noise-gate"
    DISTORTION   = "distortion"
    SATURATION   = "saturation"
    GAIN         = "gain"
    CHORUS       = "chorus"
    DELAY        = "delay"
    REVERB       = "reverb"
    NORMALIZE    = "normalize"
    PEAK_LIMIT   = "peak-limit"
    TRIM_EDGES   = "trim-edges"
    TRIM_SILENCE = "trim-silence"
    FADE_IN      = "fade-in"
    FADE_OUT     = "fade-out"

class AudioProcessorNormalizeMode(str, Enum):
    RMS  = "rms"
    PEAK = "peak"
    LUFS = "lufs"

class AudioProcessorPeakLimitMode(str, Enum):
    HARD   = "hard"
    SMOOTH = "smooth"

class CommonAudioProcessorActionConfig(CommonActionConfig):
    method: AudioProcessorActionMethod = Field(..., description="Audio processor method.")
    audio: Union[str, List[str]] = Field(..., description="Input audio(s) (file path, bytes, or variable reference).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios per batch.")
