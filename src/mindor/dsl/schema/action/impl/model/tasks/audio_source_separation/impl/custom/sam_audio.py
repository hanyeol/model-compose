from typing import Literal, Union, List, Optional
from pydantic import BaseModel, Field
from ..common import (
    AudioSourceSeparationSpan,
    CommonAudioSourceSeparationModelActionConfig,
    CommonAudioSourceSeparationParamsConfig,
)

class SamAudioAudioSourceSeparationSpan(AudioSourceSeparationSpan):
    polarity: Union[Literal["positive", "negative"], str] = Field(default="positive", description="Span polarity; 'positive' marks a span where the target sound occurs, 'negative' actively suppresses a span that does not contain the target.")

class SamAudioAudioSourceSeparationVisualPrompt(BaseModel):
    video: Union[str, List[str]] = Field(..., description="Video file providing visual context for the target sound.")
    mask: Union[str, List[str]] = Field(..., description="Mask video file aligned with `video`; non-zero regions isolate the visual object whose sound should be separated.")

class SamAudioAudioSourceSeparationParamsConfig(CommonAudioSourceSeparationParamsConfig):
    predict_spans: Union[bool, str] = Field(default=False, description="Whether to automatically predict target spans from the text description; improves non-ambience sounds at higher latency.")
    reranking_candidates: Union[int, str] = Field(default=1, description="Number of separation candidates generated per input and re-ranked; higher values improve quality at the cost of latency and memory.")

class SamAudioAudioSourceSeparationModelActionConfig(CommonAudioSourceSeparationModelActionConfig):
    visual: Optional[SamAudioAudioSourceSeparationVisualPrompt] = Field(default=None, description="Optional visual prompt pairing a video with a per-frame mask to isolate the target sound.")
    spans: Optional[Union[List[SamAudioAudioSourceSeparationSpan], str]] = Field(default=None, description="Optional time spans where the target sound occurs; each entry is `{start, end, polarity}` in seconds. Unspecified regions are treated as neutral (the model decides).")
    params: SamAudioAudioSourceSeparationParamsConfig = Field(default_factory=SamAudioAudioSourceSeparationParamsConfig, description="SAM-Audio separation quality parameters.")
