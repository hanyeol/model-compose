from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ..common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class TadaTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL of the reference audio used for voice cloning.")
    reference_text: Optional[str] = Field(default=None, description="Transcription of the reference audio; when omitted, TADA's built-in ASR is used (English only).")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")

TadaTextToSpeechModelActionConfig = Annotated[
    Union[
        TadaTextToSpeechModelCloneActionConfig,
    ],
    Field(discriminator="method")
]
