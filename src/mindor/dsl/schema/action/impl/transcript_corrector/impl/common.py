from typing import Union, Optional, List, Any
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class TranscriptGranularity(str, Enum):
    WORD      = "word"
    CHARACTER = "character"

class CommonTranscriptCorrectorActionConfig(CommonActionConfig):
    transcript: Any = Field(..., description="STT segments to correct: a list of `{text, start_time, end_time}` segments, a fragmented segment stream, or a list or stream of such transcripts for batch processing.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of transcripts processed per batch when the input is a list or stream of transcripts.")
    streaming: Union[bool, str] = Field(default=False, description="Whether corrected segments are emitted incrementally per transcript rather than collected into a list.")
    reference: Union[str, List[str]] = Field(..., description="Ground-truth reference text used to correct the STT transcript; a list of strings is joined with a single space.")
    granularity: Union[TranscriptGranularity, str] = Field(default=TranscriptGranularity.WORD, description="Reference tokenization granularity; `word` splits on letter runs, `character` emits one code point per token (recommended for CJK).")
    text_key: str = Field(default="text", description="Key on each transcript segment that holds the recognized text.")
    start_time_key: str = Field(default="start_time", description="Key on each transcript segment that holds the segment start time.")
    end_time_key: str = Field(default="end_time", description="Key on each transcript segment that holds the segment end time.")
    case_sensitive: Union[bool, str] = Field(default=False, description="Whether alignment matching distinguishes uppercase from lowercase.")
    ignore_punctuation: Union[bool, str] = Field(default=True, description="Whether punctuation is ignored during alignment matching; original punctuation from the reference is preserved in the output.")
    window_multiplier: Union[float, str] = Field(default=3.0, description="Reference search window size per STT segment, as a multiple of the segment's token count.")
    min_window_tokens: Union[int, str] = Field(default=8, description="Minimum reference window size in tokens, applied regardless of segment length.")
    match_threshold: Union[float, str] = Field(default=0.5, description="Minimum normalized similarity from 0.0 to 1.0 required to accept a match; segments below this are skipped.")
