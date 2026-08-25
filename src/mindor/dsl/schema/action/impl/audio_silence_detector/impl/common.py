from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonAudioSilenceDetectorActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to scan for silence.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")
