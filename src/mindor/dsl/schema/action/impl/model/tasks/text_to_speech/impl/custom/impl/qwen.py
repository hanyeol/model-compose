from typing import Union, Literal
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class QwenTextToSpeechModelGenerateActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: str = Field(default="vivian", description="Built-in Qwen voice name used for synthesis.")
    instructions: str = Field(default="", description="Natural-language style and emotion instructions applied to the voice.")

class QwenTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL of the reference audio used for voice cloning.")
    reference_text: str = Field(..., description="Transcription text of the reference audio.")

class QwenTextToSpeechModelDesignActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: str = Field(..., description="Natural-language description of the desired voice.")
