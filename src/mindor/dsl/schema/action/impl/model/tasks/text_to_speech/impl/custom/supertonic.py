from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ..common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class SupertonicTextToSpeechModelGenerateActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: str = Field(default="F1", description="Built-in voice style ID (M1-M5, F1-F5) or path to a Voice Builder JSON file.")
    speed: Optional[Union[float, str]] = Field(default=None, description="Speech speed multiplier; 1.0 is normal (range 0.7-2.0).")
    total_steps: Optional[Union[int, str]] = Field(default=None, description="Diffusion sampling steps; higher trades speed for quality (range 5-12, default 8).")
    max_chunk_length: Optional[Union[int, str]] = Field(default=None, description="Maximum character length per synthesis chunk.")
    silence_duration: Optional[Union[float, str]] = Field(default=None, description="Silence (seconds) inserted between synthesized chunks.")

SupertonicTextToSpeechModelActionConfig = Annotated[
    Union[
        SupertonicTextToSpeechModelGenerateActionConfig,
    ],
    Field(discriminator="method")
]
