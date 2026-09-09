from typing import Union, Literal, Optional, Annotated
from enum import Enum
from pydantic import Field
from ..common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class FireRedTextToSpeechEditMode(str, Enum):
    SEMANTIC = "semantic"
    ACOUSTIC = "acoustic"

class FireRedTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Reference audio used for zero-shot voice cloning.")
    reference_text: Optional[str] = Field(default=None, description="Transcript of the reference audio; recommended for best speaker similarity.")
    text_frontend: Union[bool, str] = Field(default=True, description="Whether FireRedTTS3's text-normalization frontend runs on the input.")

class FireRedTextToSpeechModelDesignActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: str = Field(..., description="Natural-language description of the target voice (gender, age, timbre, emotion, pace, accent).")

class FireRedTextToSpeechModelEditActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.EDIT]
    reference_audio: str = Field(..., description="Input audio to be edited.")
    instructions: str = Field(..., description="Edit instruction; free-form for semantic mode, or a template like 'adjust the speed to X' for acoustic mode.")
    mode: Union[FireRedTextToSpeechEditMode, str] = Field(default=FireRedTextToSpeechEditMode.SEMANTIC, description="Edit mode; 'semantic' for content edits, 'acoustic' for speed/pitch/volume.")

FireRedTextToSpeechModelActionConfig = Annotated[
    Union[
        FireRedTextToSpeechModelCloneActionConfig,
        FireRedTextToSpeechModelDesignActionConfig,
        FireRedTextToSpeechModelEditActionConfig,
    ],
    Field(discriminator="method")
]
