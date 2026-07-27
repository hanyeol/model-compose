from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class CosyvoiceTextToSpeechModelGenerateActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: str = Field(..., description="Preset speaker id. On CosyVoice1-SFT models this is a built-in spk_id (e.g. '中文女'); on CosyVoice2/3 it must be a zero-shot speaker previously registered via add_zero_shot_spk / save_spkinfo.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier (1.0 = natural).")
    text_frontend: Union[bool, str] = Field(default=True, description="Run CosyVoice's text normalization frontend.")

class CosyvoiceTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL to the reference audio for zero-shot voice cloning.")
    reference_text: Optional[str] = Field(default=None, description="Transcription of the reference audio. If omitted, CosyVoice's cross_lingual inference is used instead (works without a transcript).")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier (1.0 = natural).")
    text_frontend: Union[bool, str] = Field(default=True, description="Run CosyVoice's text normalization frontend.")

class CosyvoiceTextToSpeechModelDesignActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.DESIGN]
    instructions: str = Field(..., description="Natural-language instruction controlling style, dialect, emotion, etc. (e.g. '用四川话说这句话'). Passed as instruct_text to CosyVoice2/3 inference_instruct2.")
    reference_audio: str = Field(..., description="Path or URL to the reference audio. CosyVoice2/3 instruct2 requires a prompt wav to condition the target voice.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier (1.0 = natural).")
    text_frontend: Union[bool, str] = Field(default=True, description="Run CosyVoice's text normalization frontend.")

CosyvoiceTextToSpeechModelActionConfig = Annotated[
    Union[
        CosyvoiceTextToSpeechModelGenerateActionConfig,
        CosyvoiceTextToSpeechModelCloneActionConfig,
        CosyvoiceTextToSpeechModelDesignActionConfig,
    ],
    Field(discriminator="method")
]
