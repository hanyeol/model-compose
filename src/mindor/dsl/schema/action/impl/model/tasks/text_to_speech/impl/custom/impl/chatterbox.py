from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class ChatterboxTextToSpeechModelGenerateActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    exaggeration: Optional[Union[float, str]] = Field(default=None, description="Emotional exaggeration; 0.0 is monotone and 1.0 is dramatic.")
    cfg_weight: Optional[Union[float, str]] = Field(default=None, description="Classifier-free guidance weight applied during synthesis.")
    temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature controlling speech variation.")

class ChatterboxTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL of the reference audio used for voice cloning; 5 seconds or more is recommended.")
    exaggeration: Optional[Union[float, str]] = Field(default=None, description="Emotional exaggeration; 0.0 is monotone and 1.0 is dramatic.")
    cfg_weight: Optional[Union[float, str]] = Field(default=None, description="Classifier-free guidance weight applied during synthesis.")
    temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature controlling speech variation.")

ChatterboxTextToSpeechModelActionConfig = Annotated[
    Union[
        ChatterboxTextToSpeechModelGenerateActionConfig,
        ChatterboxTextToSpeechModelCloneActionConfig,
    ],
    Field(discriminator="method")
]
