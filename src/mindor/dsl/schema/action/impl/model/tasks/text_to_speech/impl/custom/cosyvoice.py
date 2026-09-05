from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ..common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class CosyvoiceTextToSpeechModelGenerateActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: str = Field(..., description="Preset speaker ID; a built-in spk_id on CosyVoice1-SFT models, or a pre-registered zero-shot speaker on CosyVoice2/3.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier; 1.0 is natural.")
    text_frontend: Union[bool, str] = Field(default=True, description="Whether CosyVoice's text normalization frontend is run on the input.")

class CosyvoiceTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Reference audio used for zero-shot voice cloning.")
    reference_text: Optional[str] = Field(default=None, description="Transcription of the reference audio; when omitted, CosyVoice's cross-lingual inference is used instead.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier; 1.0 is natural.")
    text_frontend: Union[bool, str] = Field(default=True, description="Whether CosyVoice's text normalization frontend is run on the input.")

class CosyvoiceTextToSpeechModelDesignActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: str = Field(..., description="Natural-language instruction controlling style, dialect, emotion, and similar attributes (passed as instruct_text on CosyVoice2/3).")
    reference_audio: str = Field(..., description="Prompt wav that conditions the target voice for CosyVoice2/3 instruct2.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier; 1.0 is natural.")
    text_frontend: Union[bool, str] = Field(default=True, description="Whether CosyVoice's text normalization frontend is run on the input.")

CosyvoiceTextToSpeechModelActionConfig = Annotated[
    Union[
        CosyvoiceTextToSpeechModelGenerateActionConfig,
        CosyvoiceTextToSpeechModelCloneActionConfig,
        CosyvoiceTextToSpeechModelDesignActionConfig,
    ],
    Field(discriminator="method")
]
