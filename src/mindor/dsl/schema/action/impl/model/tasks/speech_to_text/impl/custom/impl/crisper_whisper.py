from typing import Union, Literal, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonSpeechToTextModelActionConfig

class CrisperWhisperSpeechToTextParamsConfig(BaseModel):
    chunk_duration: Optional[Union[float, str]] = Field(default=None, description="Longform window length in seconds (<= 30).")
    stride: Optional[Union[float, str]] = Field(default=None, description="Seconds between chunks for longform (default 26s, i.e. 4s overlap).")
    context_words: Optional[Union[int, str]] = Field(default=None, description="Number of words from the previous chunk fed as continuation context.")
    drop_words: Optional[Union[int, str]] = Field(default=None, description="Max words dropped at each chunk boundary to avoid partial-word artefacts.")
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens generated per chunk.")

class CrisperWhisperSpeechToTextModelActionConfig(CommonSpeechToTextModelActionConfig):
    mode: Optional[Union[Literal[ "verbatim", "intended" ], str]] = Field(default="verbatim", description="'verbatim' preserves fillers/stutters/false starts; 'intended' returns a clean transcript.")
    hotwords: Optional[Union[List[str], str]] = Field(default=None, description="Domain vocabulary to bias recognition toward. Requires a Pro model; standard models emit a warning if used.")
    longform_strategy: Optional[Union[Literal[ "continuation", "chunked_lcs", "token_lcs" ], str]] = Field(default=None, description="Strategy for audio longer than 30 seconds. Defaults to 'continuation' (best quality).")
    speculative_decoding: Union[bool, str] = Field(default=False, description="Enable speculative decoding for a 1.3-1.4x speedup. Requires the ct2 backend and a draft_model configured on the component.")
    speculative_mode: Optional[Union[Literal[ "strict", "semantic" ], str]] = Field(default=None, description="'strict' preserves output exactly; 'semantic' accepts punctuation/casing differences for higher throughput.")
    hallucination_mitigation: Union[bool, str] = Field(default=True, description="Detect and repair Whisper's repetition-loop failure mode.")
    temperature_fallback: Union[bool, str] = Field(default=True, description="Re-decode with escalating temperature when a chunk collapses to near-empty output.")
    params: CrisperWhisperSpeechToTextParamsConfig = Field(default_factory=CrisperWhisperSpeechToTextParamsConfig, description="Long-form and generation tuning parameters.")
