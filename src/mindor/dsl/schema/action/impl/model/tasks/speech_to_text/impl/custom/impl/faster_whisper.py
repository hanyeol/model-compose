from typing import Union, Literal, Optional
from pydantic import BaseModel, Field
from ...common import CommonSpeechToTextModelActionConfig

class FasterWhisperSpeechToTextParamsConfig(BaseModel):
    num_beams: Union[int, str] = Field(default=1, description="Number of beams for beam search.")
    temperature: Union[float, str] = Field(default=0.0, description="Sampling temperature; 0.0 for greedy decoding.")
    compression_ratio_threshold: Union[float, str] = Field(default=2.4, description="Gzip compression ratio threshold of generated tokens.")
    logprob_threshold: Union[float, str] = Field(default=-1.0, description="Log probability threshold for filtering low-confidence segments.")
    no_speech_threshold: Union[float, str] = Field(default=0.6, description="No-speech probability threshold for skipping silent segments.")

class FasterWhisperSpeechToTextModelActionConfig(CommonSpeechToTextModelActionConfig):
    task: Optional[Union[Literal["transcribe", "translate"], str]] = Field(default="transcribe", description="Whisper task: 'transcribe' or 'translate' (translate outputs English).")
    chunk_length: Optional[Union[float, str]] = Field(default=30.0, description="Audio chunk length in seconds for long-form transcription.")
    params: FasterWhisperSpeechToTextParamsConfig = Field(default_factory=FasterWhisperSpeechToTextParamsConfig, description="Speech-to-text generation parameters.")
