from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonModelActionConfig

class TextToSpeechActionMethod(str, Enum):
    GENERATE = "generate"
    CLONE    = "clone"
    DESIGN   = "design"

class CommonTextToSpeechModelActionConfig(CommonModelActionConfig):
    method: TextToSpeechActionMethod = Field(..., description="TTS generation method.")
    text: Union[str, List[str]] = Field(..., description="Text to synthesize into speech.")
    language: Optional[Union[str, str]] = Field(default=None, description="Language of the text. Use ISO 639-1 / BCP 47 codes (e.g., 'en', 'ko', 'zh-CN').")
