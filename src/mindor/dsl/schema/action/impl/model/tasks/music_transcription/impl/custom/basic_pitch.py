from typing import Union, Optional
from pydantic import Field
from ..common import CommonMusicTranscriptionModelActionConfig, CommonMusicTranscriptionParamsConfig

class BasicPitchMusicTranscriptionParamsConfig(CommonMusicTranscriptionParamsConfig):
    minimum_note_length: Optional[Union[float, str]] = Field(default=None, description="Minimum note duration in milliseconds; shorter detections are discarded.")
    minimum_frequency: Optional[Union[float, str]] = Field(default=None, description="Lower bound of detected pitch in Hz; notes below this frequency are ignored.")
    maximum_frequency: Optional[Union[float, str]] = Field(default=None, description="Upper bound of detected pitch in Hz; notes above this frequency are ignored.")
    midi_tempo: Optional[Union[float, str]] = Field(default=None, description="Tempo (BPM) written into the MIDI header; does not affect detected timings.")

class BasicPitchMusicTranscriptionModelActionConfig(CommonMusicTranscriptionModelActionConfig):
    return_pitch_bends: Union[bool, str] = Field(default=False, description="Whether per-note pitch bend events are written into the MIDI and included as a pitch_bends array on each note.")
    params: BasicPitchMusicTranscriptionParamsConfig = Field(default_factory=BasicPitchMusicTranscriptionParamsConfig, description="Basic Pitch detection thresholds and MIDI writing options.")
