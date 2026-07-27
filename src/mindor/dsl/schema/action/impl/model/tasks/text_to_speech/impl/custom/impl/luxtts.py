from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class LuxttsTextToSpeechModelCloneActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.CLONE]
    reference_audio: str = Field(..., description="Path or URL to the reference audio for zero-shot voice cloning.")
    reference_duration: Union[int, str] = Field(default=5, description="Reference clip duration (seconds) considered during prompt encoding.")
    reference_rms: Union[float, str] = Field(default=0.01, description="Target RMS applied to the reference clip.")
    num_steps: Union[int, str] = Field(default=4, description="Flow-matching solver steps (higher = better quality, slower).")
    guidance_scale: Union[float, str] = Field(default=3.0, description="Classifier-free guidance scale.")
    t_shift: Union[float, str] = Field(default=0.5, description="Flow-matching time shift.")
    speed: Union[float, str] = Field(default=1.0, description="Speech speed multiplier (1.0 = natural).")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for reproducible generation.")

LuxttsTextToSpeechModelActionConfig = Annotated[
    Union[
        LuxttsTextToSpeechModelCloneActionConfig,
    ],
    Field(discriminator="method")
]
