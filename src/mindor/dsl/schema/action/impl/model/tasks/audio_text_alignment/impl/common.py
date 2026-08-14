from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class AudioTextAlignmentModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio path, URL, or list of audio inputs to align.")
    text: Union[str, List[str]] = Field(..., description="Reference transcripts aligned against the audio; the count must match `audio`.")
    language: Optional[str] = Field(default=None, description="Language code (e.g., en, ko) used to select the alignment model when applicable.")
    chunk_length: Union[float, str] = Field(default=30.0, description="Chunk length in seconds used to split long audio before forced alignment.")
    chunk_overlap: Union[str, float, int] = Field(default="1s", description="Overlap between adjacent chunks as a duration string (e.g., 1s, 500ms) or seconds.")
    return_confidence: Union[bool, str] = Field(default=True, description="Whether per-word alignment confidence scores are included in the result.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
