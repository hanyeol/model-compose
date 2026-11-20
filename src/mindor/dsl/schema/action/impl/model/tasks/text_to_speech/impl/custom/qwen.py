from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ..common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class QwenTextToSpeechModelGenerateActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: str = Field(default="vivian", description="Built-in Qwen voice name used for synthesis.")
    instructions: str = Field(default="", description="Natural-language style and emotion instructions applied to the voice.")

class QwenTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Reference audio used for voice cloning.")
    reference_text: str = Field(..., description="Transcription text of the reference audio.")
    temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature for the main decoder.")
    subtalker_temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature for the subtalker decoder.")
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens generated; unset uses the model's configured limit.")

class QwenTextToSpeechModelDesignActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: str = Field(..., description="Natural-language description of the desired voice.")

QwenTextToSpeechModelActionConfig = Annotated[
    Union[
        QwenTextToSpeechModelGenerateActionConfig,
        QwenTextToSpeechModelCloneActionConfig,
        QwenTextToSpeechModelDesignActionConfig,
    ],
    Field(discriminator="method")
]
