from typing import Union, Optional
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class MusicScoreLoaderFormat(str, Enum):
    MIDI     = "midi"
    MUSICXML = "musicxml"

class CommonMusicScoreLoaderActionConfig(CommonActionConfig):
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of score sources processed per batch.")
