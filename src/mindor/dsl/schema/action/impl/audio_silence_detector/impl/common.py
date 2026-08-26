from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonAudioSilenceDetectorActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to scan for silence.")
    silence_threshold: Union[float, int, str] = Field(default=-30.0, description="Silence detection threshold in dBFS.")
    min_silence_duration: Union[float, int, str] = Field(default="500ms", description="Minimum duration a quiet run must last to be reported as silence.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")
