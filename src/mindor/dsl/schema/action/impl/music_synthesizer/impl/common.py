from __future__ import annotations

from typing import Union, Literal, Optional, Dict, List, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig

class MusicSynthesizerActionMethod(str, Enum):
    SEQUENCE = "sequence"

class MusicSynthesizerInstrument(str, Enum):
    KICK        = "kick"
    SNARE       = "snare"
    HAT         = "hat"
    TICK        = "tick"
    TOM         = "tom"
    POP         = "pop"
    WHOOSH      = "whoosh"
    CHORD       = "chord"
    SUB_BASS    = "sub-bass"
    SINE        = "sine"
    NOISE_BURST = "noise-burst"

class MusicSynthesizerBeatPattern(BaseModel):
    start: Union[float, str] = Field(..., description="First beat position the pattern emits (inclusive).")
    end: Union[float, str] = Field(..., description="Beat position the pattern stops before (exclusive).")
    step: Union[float, str] = Field(default=1.0, description="Beat interval between successive events.")
    phase: Union[float, str] = Field(default=0.0, description="Beat offset added to every emitted position.")

class MusicSynthesizerTrackEventConfig(BaseModel):
    beat: Union[float, List[Union[float, str]], MusicSynthesizerBeatPattern, str] = Field(..., description="Beat position(s) this event fires at — a number, a list, or a {start, end, step} pattern.")
    instrument: MusicSynthesizerInstrument = Field(..., description="Instrument voice used to render this event.")
    length: Optional[Union[float, str]] = Field(default=None, description="Beat length used by sustained instruments such as chord and sine.")
    gain: Union[float, str] = Field(default=1.0, description="Linear gain multiplier applied to this event.")
    pan: Union[float, str] = Field(default=0.0, description="Stereo pan for this event, from -1.0 (full left) to 1.0 (full right).")
    params: Dict[str, Any] = Field(default_factory=dict, description="Instrument-specific parameters (see the instrument reference).")

class MusicSynthesizerTrackConfig(BaseModel):
    id: str = Field(..., description="Track identifier used by sidechain routing and diagnostics.")
    gain: Union[float, str] = Field(default=1.0, description="Linear gain multiplier applied to the whole track.")
    pan: Union[float, str] = Field(default=0.0, description="Stereo pan applied to the whole track, from -1.0 to 1.0.")
    events: List[Union[MusicSynthesizerTrackEventConfig, str]] = Field(default_factory=list, description="Events rendered onto this track.")

class MusicSynthesizerSidechainConfig(BaseModel):
    trigger: str = Field(..., description="Track id whose events open the ducking envelope.")
    targets: List[str] = Field(..., description="Track ids attenuated on each trigger hit.")
    depth: Union[float, str] = Field(default=0.78, description="Peak gain reduction on each hit, from 0.0 (no ducking) to 1.0 (full mute).")
    attack_time: Union[str, float] = Field(default="2ms", description="Time to reach peak reduction after each hit, as a duration string or seconds.")
    release_time: Union[str, float] = Field(default="70ms", description="Time to recover to unity gain after each hit, as a duration string or seconds.")

class MusicSynthesizerSilenceConfig(BaseModel):
    start_beat: Union[float, str] = Field(..., description="Beat position where the silence begins (inclusive).")
    end_beat: Union[float, str] = Field(..., description="Beat position where the silence ends (exclusive).")
    pre_fade_duration: Union[str, float] = Field(default="3ms", description="Fade-out duration applied just before the silence, as a duration string or seconds.")

class MusicSynthesizerFadeConfig(BaseModel):
    start_beat: Union[float, str] = Field(..., description="Beat position where the fade begins.")
    end_beat: Union[float, str] = Field(..., description="Beat position where the fade ends.")
    curve: Literal[ "linear", "quadratic" ] = Field(default="quadratic", description="Fade curve shape applied over the range.")

class MusicSynthesizerMasterConfig(BaseModel):
    soft_clip: Union[float, str] = Field(default=1.2, description="Pre-tanh drive amount for the soft-clip stage; 0 disables clipping.")
    normalize_level: Optional[Union[float, str]] = Field(default=-1.0, description="Target peak level in dBFS after normalization; null disables normalization.")
    silences: List[Union[MusicSynthesizerSilenceConfig, str]] = Field(default_factory=list, description="Hard-silence windows applied after mastering.")
    fades: List[Union[MusicSynthesizerFadeConfig, str]] = Field(default_factory=list, description="Fade windows applied after mastering.")

class CommonMusicSynthesizerActionConfig(CommonActionConfig):
    method: MusicSynthesizerActionMethod = Field(..., description="Synthesis operation this action performs.")
    streaming: Union[bool, str] = Field(default=False, description="Whether the synthesized output is emitted as a byte stream instead of a temporary file.")

class MusicSynthesizerSequenceActionConfig(CommonMusicSynthesizerActionConfig):
    method: Literal[MusicSynthesizerActionMethod.SEQUENCE]
    tracks: Union[List[List[MusicSynthesizerTrackConfig]], List[MusicSynthesizerTrackConfig], str] = Field(..., description="Tracks whose events make up the mix.")
    beats: Union[List[float], float, str] = Field(..., description="Total length of the piece in beats.")
    bpm: Union[float, str] = Field(..., description="Tempo in beats per minute; drives the beat-to-time conversion.")
    sample_rate: Union[int, str] = Field(default=48000, description="Output sample rate in Hz (e.g., 44100, 48000).")
    channels: Union[int, str] = Field(default=2, description="Output channel count (1 for mono, 2 for stereo).")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for reproducible noise-based instruments; null for non-deterministic output.")
    master: Union[MusicSynthesizerMasterConfig, str] = Field(default_factory=MusicSynthesizerMasterConfig, description="Master-bus soft-clip, normalization, silence and fade shaping.")
    sidechain: Optional[Union[MusicSynthesizerSidechainConfig, str]] = Field(default=None, description="Kick-driven ducking applied to selected tracks before summing.")

    @model_validator(mode="after")
    def validate_tracks(self) -> MusicSynthesizerSequenceActionConfig:
        if isinstance(self.tracks, list):
            ids = [ track.id for track in self.tracks if isinstance(track, MusicSynthesizerTrackConfig) ]
            duplicates = { track_id for track_id in ids if ids.count(track_id) > 1 }
            if duplicates:
                raise ValueError(f"Duplicate track ids: {sorted(duplicates)}")

            if self.sidechain and isinstance(self.sidechain, MusicSynthesizerSidechainConfig):
                known = set(ids)
                if self.sidechain.trigger not in known:
                    raise ValueError(f"Sidechain trigger '{self.sidechain.trigger}' does not match any track id.")
                missing = [ target for target in self.sidechain.targets if target not in known ]
                if missing:
                    raise ValueError(f"Sidechain targets not found among tracks: {missing}")

        return self
