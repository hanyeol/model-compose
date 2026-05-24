from typing import Union, Literal
from pydantic import Field
from ..common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class QwenTextToSpeechGenerateModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: Union[str, str] = Field(default="vivian", description="Built-in voice name.")
    instructions: Union[str, str] = Field(default="", description="Emotion/style instructions for the voice.")

class QwenTextToSpeechCloneModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: Union[str, str] = Field(..., description="Path or URL to the reference audio for voice cloning.")
    reference_text: Union[str, str] = Field(..., description="Transcription text of the reference audio.")

class QwenTextToSpeechDesignModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: Union[str, str] = Field(..., description="Description of the desired voice.")
