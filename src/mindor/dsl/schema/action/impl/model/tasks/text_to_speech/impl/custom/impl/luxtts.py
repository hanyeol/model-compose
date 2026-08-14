from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class LuxttsTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL of the reference audio used for zero-shot voice cloning.")
    reference_duration: Union[int, str] = Field(default=5, description="Reference clip duration in seconds considered during prompt encoding.")
    reference_rms: Union[float, str] = Field(default=0.01, description="Target RMS the reference clip is normalized to.")
    num_steps: Union[int, str] = Field(default=4, description="Number of flow-matching solver steps; higher values improve quality at the cost of speed.")
    guidance_scale: Union[float, str] = Field(default=3.0, description="Classifier-free guidance scale applied during synthesis.")
    t_shift: Union[float, str] = Field(default=0.5, description="Flow-matching time shift applied by the solver.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier; 1.0 is natural.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")

LuxttsTextToSpeechModelActionConfig = Annotated[
    Union[
        LuxttsTextToSpeechModelCloneActionConfig,
    ],
    Field(discriminator="method")
]
