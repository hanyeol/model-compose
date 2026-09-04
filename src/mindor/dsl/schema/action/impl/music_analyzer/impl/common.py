from __future__ import annotations

from typing import Union, Literal, Optional, List, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from ...common import CommonActionConfig

class MusicAnalyzerMetric(str, Enum):
    BEATS        = "beats"
    ONSETS       = "onsets"
    TEMPOGRAM    = "tempogram"
    ACTIVITY     = "activity"
    KEY          = "key"
    CHROMA       = "chroma"
    TONNETZ      = "tonnetz"
    BRIGHTNESS   = "brightness"
    FLATNESS     = "flatness"
    HARMONICITY  = "harmonicity"

class CommonMusicAnalyzerActionConfig(CommonActionConfig):
    metric: MusicAnalyzerMetric = Field(..., description="Kind of measurement performed on the music.")
    audio: Optional[Union[str, List[str]]] = Field(default=None, description="Audio source or list of sources to analyze.")
    spectrum: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Pre-computed spectrum from audio-feature-extractor; provide instead of `audio` to reuse features across metrics.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Optional resample target for `audio` input; when omitted the file's native rate is used. Ignored when `spectrum` is provided.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")

    @model_validator(mode="after")
    def validate_audio_or_spectrum(self) -> CommonMusicAnalyzerActionConfig:
        if (self.audio is None) == (self.spectrum is None):
            raise ValueError("Exactly one of `audio` or `spectrum` must be provided.")
        return self

class MusicAnalyzerBeatsActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.BEATS]
    min_bpm: Union[float, int, str] = Field(default=60.0, description="Lowest BPM considered when tracking beats.")
    max_bpm: Union[float, int, str] = Field(default=200.0, description="Highest BPM considered when tracking beats.")

class MusicAnalyzerOnsetsActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.ONSETS]
    min_gap: Union[float, int, str] = Field(default="30ms", description="Minimum time between adjacent onsets; closer peaks are suppressed.")

class MusicAnalyzerTempogramActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.TEMPOGRAM]
    min_bpm: Union[float, int, str] = Field(default=60.0, description="Lowest BPM axis value in the tempogram.")
    max_bpm: Union[float, int, str] = Field(default=200.0, description="Highest BPM axis value in the tempogram.")

class MusicAnalyzerActivityActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.ACTIVITY]
    min_duration: Union[float, int, str] = Field(default="0.3s", description="Minimum duration of an active region; shorter runs are dropped as noise.")
    level: Union[float, int, str] = Field(default=0.35, description="Threshold within the song's own quiet-to-loud range above which audio is considered active.")

class MusicAnalyzerKeyActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.KEY]

class MusicAnalyzerChromaActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.CHROMA]

class MusicAnalyzerTonnetzActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.TONNETZ]

class MusicAnalyzerBrightnessActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.BRIGHTNESS]

class MusicAnalyzerFlatnessActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.FLATNESS]

class MusicAnalyzerHarmonicityActionConfig(CommonMusicAnalyzerActionConfig):
    metric: Literal[MusicAnalyzerMetric.HARMONICITY]
