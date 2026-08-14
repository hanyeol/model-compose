from typing import Union, Literal, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonSpeechToTextModelActionConfig

class CrisperWhisperSpeechToTextParamsConfig(BaseModel):
    chunk_duration: Optional[Union[float, str]] = Field(default=None, description="Long-form window length in seconds, no more than 30.")
    stride: Optional[Union[float, str]] = Field(default=None, description="Seconds between successive long-form chunks; the default 26s implies a 4s overlap.")
    context_words: Optional[Union[int, str]] = Field(default=None, description="Number of words from the previous chunk fed as continuation context.")
    drop_words: Optional[Union[int, str]] = Field(default=None, description="Maximum words dropped at each chunk boundary to avoid partial-word artifacts.")
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens generated per chunk.")

class CrisperWhisperSpeechToTextModelActionConfig(CommonSpeechToTextModelActionConfig):
    mode: Optional[Union[Literal[ "verbatim", "intended" ], str]] = Field(default="verbatim", description="Transcription style; `verbatim` preserves fillers and stutters, `intended` returns a clean transcript.")
    hotwords: Optional[Union[List[str], str]] = Field(default=None, description="Domain vocabulary that biases recognition; requires a Pro model, standard models emit a warning.")
    longform_strategy: Optional[Union[Literal[ "continuation", "chunked_lcs", "token_lcs" ], str]] = Field(default=None, description="Strategy for audio longer than 30 seconds; defaults to `continuation` for best quality.")
    speculative_decoding: Union[bool, str] = Field(default=False, description="Whether speculative decoding is enabled for a 1.3-1.4x speedup; requires the ct2 backend and a component-level `draft_model`.")
    speculative_mode: Optional[Union[Literal[ "strict", "semantic" ], str]] = Field(default=None, description="Speculative-decoding acceptance mode; `strict` preserves output exactly, `semantic` accepts punctuation and casing differences for throughput.")
    hallucination_mitigation: Union[bool, str] = Field(default=True, description="Whether Whisper's repetition-loop failure mode is detected and repaired.")
    temperature_fallback: Union[bool, str] = Field(default=True, description="Whether chunks are re-decoded with escalating temperature when output collapses to near-empty.")
    params: CrisperWhisperSpeechToTextParamsConfig = Field(default_factory=CrisperWhisperSpeechToTextParamsConfig, description="Long-form and generation tuning parameters.")
