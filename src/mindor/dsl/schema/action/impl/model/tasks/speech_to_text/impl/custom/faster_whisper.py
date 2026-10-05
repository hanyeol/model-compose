from typing import Union, Literal, Optional
from pydantic import BaseModel, Field
from ..common import CommonSpeechToTextModelActionConfig

class FasterWhisperVadParametersConfig(BaseModel):
    threshold: Union[float, str] = Field(default=0.5, description="Silero VAD speech probability threshold.")
    neg_threshold: Optional[Union[float, str]] = Field(default=None, description="Lower threshold for ending a speech region; defaults to `threshold - 0.15`.")
    min_speech_duration_ms: Union[int, str] = Field(default=0, description="Minimum duration in ms for a region to be kept as speech.")
    max_speech_duration_s: Optional[Union[float, str]] = Field(default=None, description="Maximum duration in seconds for a single speech region; longer regions are split.")
    min_silence_duration_ms: Union[int, str] = Field(default=2000, description="Minimum silence duration in ms between speech regions.")
    speech_pad_ms: Union[int, str] = Field(default=400, description="Padding in ms added to each side of a speech region.")

class FasterWhisperSpeechToTextParamsConfig(BaseModel):
    num_beams: Union[int, str] = Field(default=1, description="Number of beams used in beam search.")
    temperature: Union[float, str] = Field(default=0.0, description="Sampling temperature; 0.0 uses greedy decoding.")
    compression_ratio_threshold: Union[float, str] = Field(default=2.4, description="Gzip compression ratio above which a segment is considered degenerate and dropped.")
    log_prob_threshold: Union[float, str] = Field(default=-1.0, description="Average log-probability below which a segment is treated as low-confidence and filtered.")
    no_speech_threshold: Union[float, str] = Field(default=0.6, description="No-speech probability above which a segment is skipped as silent.")
    vad_filter: Union[bool, str] = Field(default=False, description="Enable Silero VAD to drop silent or non-speech regions before decoding.")
    vad_parameters: Optional[FasterWhisperVadParametersConfig] = Field(default=None, description="Silero VAD tuning; only used when `vad_filter` is true.")
    condition_on_previous_text: Union[bool, str] = Field(default=True, description="Feed prior segment text as prompt to the next window; disable to reduce repetition after silence.")

class FasterWhisperSpeechToTextModelActionConfig(CommonSpeechToTextModelActionConfig):
    task: Optional[Union[Literal["transcribe", "translate"], str]] = Field(default="transcribe", description="Whisper task; `transcribe` keeps the source language, `translate` outputs English.")
    chunk_length: Optional[Union[float, str]] = Field(default=30.0, description="Chunk length in seconds used to split audio for long-form transcription.")
    params: FasterWhisperSpeechToTextParamsConfig = Field(default_factory=FasterWhisperSpeechToTextParamsConfig, description="Faster-Whisper decoding parameters used for speech-to-text.")
