from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class SpeechToTextParamsConfig(BaseModel):
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens to generate. None uses the model's configured limit.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams for beam search.")
    temperature: Union[float, str] = Field(default=0.0, description="Sampling temperature; 0.0 for greedy decoding.")
    compression_ratio_threshold: Union[float, str] = Field(default=2.4, description="Gzip compression ratio threshold of generated tokens.")
    logprob_threshold: Union[float, str] = Field(default=-1.0, description="Log probability threshold for filtering low-confidence segments.")
    no_speech_threshold: Union[float, str] = Field(default=0.6, description="No-speech probability threshold for skipping silent segments.")
    return_timestamps: Union[bool, str] = Field(default=False, description="Whether to return word- or segment-level timestamps.")

class SpeechToTextModelActionConfig(CommonModelActionConfig):
    audio: Union[Union[str, List[str]], str] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    language: Optional[str] = Field(default=None, description="Language code (e.g. 'en', 'ko'). None for auto-detection.")
    task: Optional[str] = Field(default="transcribe", description="Task: 'transcribe' or 'translate'.")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    chunk_length: Optional[Union[float, str]] = Field(default=30.0, description="Audio chunk length in seconds for long-form transcription.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream transcribed tokens as they are produced.")
    params: SpeechToTextParamsConfig = Field(default_factory=SpeechToTextParamsConfig, description="Speech-to-text generation parameters.")
