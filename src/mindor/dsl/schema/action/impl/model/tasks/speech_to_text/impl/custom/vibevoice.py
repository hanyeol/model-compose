from typing import Union, Optional
from pydantic import Field
from ..common import CommonSpeechToTextModelActionConfig

class VibeVoiceSpeechToTextModelActionConfig(CommonSpeechToTextModelActionConfig):
    context_info: Optional[str] = Field(default=None, description="Hotwords or domain terms that bias recognition, comma-separated (e.g., \"Microsoft,VibeVoice\").")
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens generated; per chunk on streaming checkpoints (default 256), total on non-streaming checkpoints (default 32768).")
    temperature: Union[float, str] = Field(default=0.0, description="Sampling temperature; 0.0 uses greedy decoding.")
    top_p: Union[float, str] = Field(default=1.0, description="Nucleus sampling probability; only applied on non-streaming checkpoints when temperature > 0.")
    num_beams: Union[int, str] = Field(default=1, description="Beam search width; only applied on non-streaming checkpoints.")
