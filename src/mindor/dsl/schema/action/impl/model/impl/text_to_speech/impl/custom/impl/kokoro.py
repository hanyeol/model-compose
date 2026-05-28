from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import CommonTextToSpeechModelActionConfig, TextToSpeechActionMethod

class KokoroTextToSpeechGenerateModelActionConfig(CommonTextToSpeechModelActionConfig):
    method: Literal[TextToSpeechActionMethod.GENERATE]
    voice: Union[str, str] = Field(default="af_heart", description="Voice ID (e.g. 'af_heart', 'af_bella', 'am_michael').")
    speed: Optional[Union[float, str]] = Field(default=None, description="Speech speed multiplier (1.0 = normal).")

KokoroTextToSpeechModelActionConfig = Annotated[
    Union[
        KokoroTextToSpeechGenerateModelActionConfig,
    ],
    Field(discriminator="method")
]
