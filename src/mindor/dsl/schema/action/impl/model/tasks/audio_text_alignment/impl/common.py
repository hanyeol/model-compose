from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class AudioTextAlignmentParamsConfig(BaseModel):
    return_confidence: Union[bool, str] = Field(default=True, description="Whether to include per-word alignment confidence scores.")

class AudioTextAlignmentModelActionConfig(CommonModelActionConfig):
    audio: Union[Union[str, List[str]], str] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    text: Union[Union[str, List[str]], str] = Field(..., description="Reference transcript(s) to align against the audio. Must match the number of audio inputs.")
    language: Optional[str] = Field(default=None, description="Language code (e.g. 'en', 'ko'). Used to pick the alignment model when applicable.")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    chunk_length: Union[float, str] = Field(default=30.0, description="Audio chunk length in seconds for long-form alignment. Audio longer than this is split, forwarded chunk-by-chunk, and the emissions are stitched back together before forced alignment.")
    chunk_overlap: Union[str, float, int] = Field(default="1s", description="Overlap duration between adjacent chunks (e.g. '1s', '500ms'). Prevents context loss at chunk boundaries.")
    params: AudioTextAlignmentParamsConfig = Field(default_factory=AudioTextAlignmentParamsConfig, description="Audio-text alignment parameters.")
