from typing import Literal, Union, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class PitchUnit(str, Enum):
    HZ       = "hz"
    SEMITONE = "semitone"

class CommonMusicPitchEstimationParamsConfig(BaseModel):
    reduction: Literal["alwa", "argmax", "weighted"] = Field(default="alwa", description="Decoding rule converting activations to pitch (alwa is argmax-local weighted averaging).")
    pitch_unit: PitchUnit = Field(default=PitchUnit.HZ, description="Unit for the reported pitch value — Hz (frequency) or semitones (fractional MIDI distance from MIDI 0).")
    num_chunks: Union[int, str] = Field(default=1, description="Split CQT frames into N sequential chunks to limit GPU memory (torch backend, non-streaming only).")

class CommonMusicPitchEstimationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to estimate pitch from, or a list of audios.")
    return_activations: Union[bool, str] = Field(default=False, description="Whether per-frame activation vectors over pitch bins are included in the result.")
    return_metadata: Union[bool, str] = Field(default=True, description="Whether processing metadata (duration, sample_rate, ...) is included in the result.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch (non-streaming only).")
    streaming: Union[bool, str] = Field(default=False, description="Whether per-frame pitch results are emitted incrementally as they are produced; requires the component to have 'streaming' enabled or backend=onnx.")
    params: CommonMusicPitchEstimationParamsConfig = Field(default_factory=CommonMusicPitchEstimationParamsConfig, description="Pitch estimation parameters applied to the model.")
