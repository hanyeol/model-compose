from typing import Union, Annotated
from enum import Enum
from pydantic import Field

class CustomTextToSpeechModelFamily(str, Enum):
    QWEN = "qwen"

from .qwen import QwenTextToSpeechModelComponentConfig

CustomTextToSpeechModelComponentConfig = Annotated[
    Union[
        QwenTextToSpeechModelComponentConfig,
    ],
    Field(discriminator="family")
]
