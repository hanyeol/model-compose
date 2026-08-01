from typing import Union
from .impl import *

SpeechToTextModelActionConfig = Union[
    HuggingfaceSpeechToTextModelActionConfig,
    CustomSpeechToTextModelActionConfig,
]
