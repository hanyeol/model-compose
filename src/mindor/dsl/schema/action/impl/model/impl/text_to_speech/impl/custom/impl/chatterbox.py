from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class ChatterboxTextToSpeechGenerateModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    exaggeration: Optional[Union[float, str]] = Field(default=None, description="Emotional exaggeration (0.0 = monotone, 1.0 = dramatic).")
    cfg_weight: Optional[Union[float, str]] = Field(default=None, description="Classifier-free guidance weight controlling how closely the output mimics the reference voice.")
    temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature for controlling speech variation.")

class ChatterboxTextToSpeechCloneModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: Union[str, str] = Field(..., description="Path or URL to reference audio for voice cloning (5+ seconds recommended).")
    exaggeration: Optional[Union[float, str]] = Field(default=None, description="Emotional exaggeration (0.0 = monotone, 1.0 = dramatic).")
    cfg_weight: Optional[Union[float, str]] = Field(default=None, description="Classifier-free guidance weight controlling how closely the output mimics the reference voice.")
    temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature for controlling speech variation.")

ChatterboxTextToSpeechModelActionConfig = Annotated[
    Union[
        ChatterboxTextToSpeechGenerateModelActionConfig,
        ChatterboxTextToSpeechCloneModelActionConfig,
    ],
    Field(discriminator="method")
]
