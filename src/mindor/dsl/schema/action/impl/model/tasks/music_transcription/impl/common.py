from typing import Union, List, Optional
from pydantic import BaseModel, Field, model_validator
from ...common import CommonModelActionConfig

class CommonMusicTranscriptionParamsConfig(BaseModel):
    onset_threshold: Optional[Union[float, str]] = Field(default=None, description="Confidence threshold for detecting a note onset, from 0.0 to 1.0; higher values keep only the most confident onsets.")
    frame_threshold: Optional[Union[float, str]] = Field(default=None, description="Confidence threshold for sustaining a note across frames, from 0.0 to 1.0.")

class CommonMusicTranscriptionModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to transcribe, or a list of audios.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    return_midi: Union[bool, str] = Field(default=True, description="Whether the rendered MIDI file is included in the result.")
    return_notes: Union[bool, str] = Field(default=False, description="Whether the per-note event list is included in the result.")
    return_metadata: Union[bool, str] = Field(default=True, description="Whether processing metadata (duration, ...) is included in the result.")
    params: CommonMusicTranscriptionParamsConfig = Field(default_factory=CommonMusicTranscriptionParamsConfig, description="Detection thresholds applied to the transcriber.")

    @model_validator(mode="after")
    def validate_return_midi_or_notes(self):
        if self.return_midi is False and self.return_notes is False:
            raise ValueError("Either 'return_midi' or 'return_notes' must be true.")
        return self
