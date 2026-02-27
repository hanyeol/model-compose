from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class QwenTextToSpeechGenerateModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: Union[str, str] = Field(default="vivian", description="Built-in voice name.")
    instructions: Union[str, str] = Field(default="", description="Emotion/style instructions for the voice.")

class QwenTextToSpeechCloneModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    ref_audio: Union[str, str] = Field(..., description="Path or URL to the reference audio for voice cloning.")
    ref_text: Union[str, str] = Field(..., description="Transcription text of the reference audio.")

class QwenTextToSpeechDesignModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: Union[str, str] = Field(..., description="Description of the desired voice.")
