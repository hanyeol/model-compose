from __future__ import annotations

from typing import Union, Literal, Optional, List, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig
from ...media import AudioEncoderConfig

class AudioMixerActionMethod(str, Enum):
    CONCAT  = "concat"
    OVERLAY = "overlay"

class AudioMixerOverlayDurationMode(str, Enum):
    BASE     = "base"
    LONGEST  = "longest"
    SHORTEST = "shortest"

class AudioOverlayPlacement(BaseModel):
    start_time: Optional[Union[str, float]] = Field(default=None, description="Time the overlay first plays, as a duration string (e.g., \"2s\") or seconds.")
    end_time: Optional[Union[str, float]] = Field(default=None, description="Time the overlay stops playing, as a duration string (e.g., \"5s\") or seconds.")
    gain: Union[float, str] = Field(default=1.0, description="Linear volume multiplier for the overlay (1.0 = unchanged).")
    pan: Union[float, str] = Field(default=0.0, description="Stereo pan for the overlay, from -1.0 (full left) to 1.0 (full right).")
    fade_in: Optional[Union[str, float]] = Field(default=None, description="Fade-in duration applied at the overlay's start, as a duration string or seconds.")
    fade_out: Optional[Union[str, float]] = Field(default=None, description="Fade-out duration applied before the overlay's end, as a duration string or seconds.")

class CommonAudioMixerActionConfig(CommonActionConfig):
    method: AudioMixerActionMethod = Field(..., description="Mixing operation this action performs.")
    format: Optional[str] = Field(default=None, description="Output container format (e.g., wav, mp3, aac, flac, opus).")
    encoding: Optional[AudioEncoderConfig] = Field(default=None, description="Encoder settings applied to the mixed output.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sets processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether the mixed output is emitted as a byte stream instead of a temporary file.")

class AudioMixerConcatActionConfig(CommonAudioMixerActionConfig):
    method: Literal[AudioMixerActionMethod.CONCAT]
    audios: Union[List[str], str] = Field(..., description="Audios to concatenate, in the order they appear in the output.")
    crossfade: Optional[Union[str, float]] = Field(default=None, description="Crossfade duration between adjacent audios, as a duration string (e.g., \"500ms\") or seconds.")

    @model_validator(mode="after")
    def validate_audios(self) -> AudioMixerConcatActionConfig:
        if isinstance(self.audios, list) and len(self.audios) < 2:
            raise ValueError("'audios' must contain at least two entries for concat.")
        return self

class AudioMixerOverlayActionConfig(CommonAudioMixerActionConfig):
    method: Literal[AudioMixerActionMethod.OVERLAY]
    audio: Union[str, List[str]] = Field(..., description="Base audio the overlays are mixed on. A list runs one output per base.")
    overlay: List[str] = Field(..., description="Overlay audios mixed into the base, all playing simultaneously.")
    placement: Union[List[AudioOverlayPlacement], AudioOverlayPlacement, List[str]] = Field(default_factory=lambda: [ AudioOverlayPlacement() ], description="Placement per overlay. A single object broadcasts to every overlay; a list matches overlays by position.")
    duration_mode: Union[AudioMixerOverlayDurationMode, str] = Field(default=AudioMixerOverlayDurationMode.BASE, description="Output duration policy relative to the base and overlays.")

    @model_validator(mode="before")
    @classmethod
    def inflate_single_overlay(cls, values: Any) -> Any:
        # Normalize `overlay` and `placement` into lists so downstream always sees
        # paired lists. A single str `overlay` becomes `[overlay]`; a single
        # placement dict/object becomes `[placement]`. Template refs (str for
        # placement) are handled at render time.
        if not isinstance(values, dict):
            return values

        overlay   = values.get("overlay")
        placement = values.get("placement")

        if isinstance(overlay, str):
            values["overlay"] = [ overlay ]

        if isinstance(placement, (dict, str)):
            values["placement"] = [ placement ]

        return values
