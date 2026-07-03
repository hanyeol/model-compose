from typing import Union, Annotated
from pydantic import Field
from .impl.faster_whisper import FasterWhisperSpeechToTextModelComponentConfig

CustomSpeechToTextModelComponentConfig = Annotated[
    Union[
        FasterWhisperSpeechToTextModelComponentConfig,
    ],
    Field(discriminator="family")
]
