from typing import Union, Literal, Optional
from pydantic import BaseModel, Field
from ..common import CommonSpeechToTextModelActionConfig

class FasterWhisperSpeechToTextParamsConfig(BaseModel):
    num_beams: Union[int, str] = Field(default=1, description="Number of beams used in beam search.")
    temperature: Union[float, str] = Field(default=0.0, description="Sampling temperature; 0.0 uses greedy decoding.")
    compression_ratio_threshold: Union[float, str] = Field(default=2.4, description="Gzip compression ratio above which a segment is considered degenerate and dropped.")
    log_prob_threshold: Union[float, str] = Field(default=-1.0, description="Average log-probability below which a segment is treated as low-confidence and filtered.")
    no_speech_threshold: Union[float, str] = Field(default=0.6, description="No-speech probability above which a segment is skipped as silent.")

class FasterWhisperSpeechToTextModelActionConfig(CommonSpeechToTextModelActionConfig):
    task: Optional[Union[Literal["transcribe", "translate"], str]] = Field(default="transcribe", description="Whisper task; `transcribe` keeps the source language, `translate` outputs English.")
    chunk_length: Optional[Union[float, str]] = Field(default=30.0, description="Chunk length in seconds used to split audio for long-form transcription.")
    params: FasterWhisperSpeechToTextParamsConfig = Field(default_factory=FasterWhisperSpeechToTextParamsConfig, description="Faster-Whisper decoding parameters used for speech-to-text.")
