from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class TadaTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL to the reference audio for voice cloning.")
    reference_text: Optional[str] = Field(default=None, description="Transcription of the reference audio. If omitted, TADA's built-in ASR is used (English only).")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for reproducible generation.")

TadaTextToSpeechModelActionConfig = Annotated[
    Union[
        TadaTextToSpeechModelCloneActionConfig,
    ],
    Field(discriminator="method")
]
