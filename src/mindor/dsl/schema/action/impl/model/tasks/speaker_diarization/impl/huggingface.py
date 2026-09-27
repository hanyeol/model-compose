from typing import Union, Literal, Optional
from pydantic import Field
from .common import SpeakerDiarizationModelActionConfig

class HuggingfaceSpeakerDiarizationModelActionConfig(SpeakerDiarizationModelActionConfig):
    streaming_latency: Optional[Union[Literal[ "low", "very_low", "ultra_low" ], str]] = Field(default=None, description="Streaming latency preset; unset runs offline diarization on the full audio.")
