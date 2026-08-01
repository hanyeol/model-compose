from typing import Union, Optional, List, Any
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class TranscriptGranularity(str, Enum):
    WORD      = "word"
    CHARACTER = "character"

class CommonTranscriptCorrectorActionConfig(CommonActionConfig):
    transcript: Any = Field(..., description="STT segments to correct. A single transcript is a list of segments shaped like {text, start_time, end_time}, or a fragmented segment stream (StreamChunkIterator with is_fragmented=True). Extra keys are preserved on the output. Passing a list/stream whose elements are themselves transcripts processes multiple transcripts in one call, mirroring sentence-splitter batch semantics.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of transcripts per batch when the input is a list or stream of transcripts.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream corrected segments per transcript instead of collecting them into a list. Has no effect on the outer transcript batch shape.")
    reference: Union[str, List[str]] = Field(..., description="Ground-truth reference text used to correct the STT transcript. Must be fully available before feeding transcript segments. A list is joined with a single space.")
    granularity: Union[TranscriptGranularity, str] = Field(default=TranscriptGranularity.WORD, description="Reference tokenization granularity. 'word' splits on Unicode letter runs; 'character' emits one code point per token (recommended for CJK/scripts without spaces).")
    text_key: str = Field(default="text", description="Key holding the recognized text on each transcript segment.")
    start_time_key: str = Field(default="start_time", description="Key holding the segment start time.")
    end_time_key: str = Field(default="end_time", description="Key holding the segment end time.")
    case_sensitive: Union[bool, str] = Field(default=False, description="Whether alignment matching is case-sensitive.")
    ignore_punctuation: Union[bool, str] = Field(default=True, description="Whether punctuation is ignored during alignment matching. Original punctuation from the reference is preserved in the output text.")
    window_multiplier: Union[float, str] = Field(default=3.0, description="Size of the reference search window per STT segment, as a multiple of the segment's token count. Larger windows tolerate more STT drop-outs but cost more compute.")
    min_window_tokens: Union[int, str] = Field(default=8, description="Minimum reference window size in tokens, regardless of segment length. Ensures very short segments still see enough context to anchor.")
    match_threshold: Union[float, str] = Field(default=0.5, description="Minimum normalized similarity (0.0-1.0) required to accept a match. Segments whose best match falls below this are skipped.")
