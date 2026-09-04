from typing import Union, Optional
from pydantic import Field
from ...common import CommonMusicTranscriptionModelActionConfig, CommonMusicTranscriptionParamsConfig

class PianoTranscriptionMusicTranscriptionParamsConfig(CommonMusicTranscriptionParamsConfig):
    offset_threshold: Optional[Union[float, str]] = Field(default=None, description="Confidence threshold for detecting a note offset, from 0.0 to 1.0.")
    pedal_offset_threshold: Optional[Union[float, str]] = Field(default=None, description="Confidence threshold for detecting sustain-pedal release events, from 0.0 to 1.0.")

class PianoTranscriptionMusicTranscriptionModelActionConfig(CommonMusicTranscriptionModelActionConfig):
    params: PianoTranscriptionMusicTranscriptionParamsConfig = Field(default_factory=PianoTranscriptionMusicTranscriptionParamsConfig, description="Piano Transcription note and pedal detection thresholds.")
