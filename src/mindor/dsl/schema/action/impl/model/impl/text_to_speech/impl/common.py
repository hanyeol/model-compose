from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class TextToSpeechActionMethod(str, Enum):
    GENERATE = "generate"
    CLONE    = "clone"
    DESIGN   = "design"

class CommonTextToSpeechModelActionConfig(CommonModelActionConfig):
    method: TextToSpeechActionMethod = Field(..., description="TTS generation method.")
    text: Union[str, List[str]] = Field(..., description="Text to synthesize into speech.")
    language: Optional[Union[str, str]] = Field(default=None, description="Language of the text.")
