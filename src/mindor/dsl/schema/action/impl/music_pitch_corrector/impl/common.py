from __future__ import annotations

from typing import Union, Literal, Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class MusicPitchCorrectorActionMethod(str, Enum):
    CORRECT = "correct"
    PLAN    = "plan"
    APPLY   = "apply"

class PitchUnit(str, Enum):
    HZ       = "hz"
    SEMITONE = "semitone"

class MusicPitchCorrectionMode(str, Enum):
    SCALE  = "scale"
    MELODY = "melody"

class MusicPitchCorrectionScale(str, Enum):
    MAJOR     = "major"
    MINOR     = "minor"
    CHROMATIC = "chromatic"

class MusicPitchCorrectionAlignMode(str, Enum):
    DTW = "dtw"

class MusicPitchCorrectionOutOfRangeMode(str, Enum):
    KEEP = "keep"
    SNAP = "snap"

class MusicPitchCorrectorParamsConfig(BaseModel):
    strength: Union[float, str] = Field(default=0.8, description="Pull factor toward the target pitch (0.0 to 1.0).")
    retune_speed: Union[str, float] = Field(default="40ms", description="Time constant to reach the target pitch; 0ms is instantaneous.")
    tolerance_cents: Union[float, str] = Field(default=10.0, description="Deviations within this many cents are left untouched.")
    max_correction_cents: Union[float, str] = Field(default=250.0, description="Notes farther than this from any target are treated as out-of-range.")
    out_of_range: Union[MusicPitchCorrectionOutOfRangeMode, str] = Field(default=MusicPitchCorrectionOutOfRangeMode.KEEP, description="How to handle out-of-range notes.")
    preserve_vibrato: Union[bool, str] = Field(default=True, description="Keep intra-note vibrato (~4-8Hz) instead of flattening it to the target.")
    transition: Union[str, float] = Field(default="60ms", description="Edge window at note boundaries where correction is attenuated.")
    min_note_duration: Union[str, float] = Field(default="80ms", description="Fragments shorter than this are merged with neighbours during segmentation.")
    min_confidence: Union[float, str] = Field(default=0.5, description="Frames below this pitch confidence are excluded from correction.")
    reference_pitch: Union[float, str] = Field(default=440.0, description="Reference frequency for A4 in Hz.")

class CommonMusicPitchCorrectorActionConfig(CommonActionConfig):
    method: MusicPitchCorrectorActionMethod = Field(..., description="Pitch-correction operation this action performs.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of audios processed per batch when the input is a list or stream.")

class CommonMusicPitchCorrectorCorrectActionConfig(CommonMusicPitchCorrectorActionConfig):
    method: Literal[MusicPitchCorrectorActionMethod.CORRECT]
    pitch: Union[List[List[Dict[str, Any]]], List[Dict[str, Any]], str] = Field(..., description="Pitch frames (list of `{time, pitch, confidence?}` dicts) from music-pitch-estimation or a compatible estimator.")
    audio: Union[str, List[str]] = Field(..., description="Vocal recording to resynthesize with corrected pitch.")
    key: Optional[Union[List[str], str]] = Field(default=None, description="Tonic for `mode: scale` (e.g. 'A', 'F#'). From music-analyzer key output.")
    scale: Union[List[List[int]], List[MusicPitchCorrectionScale], List[int], MusicPitchCorrectionScale, str] = Field(default=MusicPitchCorrectionScale.MAJOR, description="Scale name or pitch-class list for `mode: scale`.")
    melody: Optional[Union[List[List[Dict[str, Any]]], List[Dict[str, Any]], str]] = Field(default=None, description="Reference melody (notes list or MIDI path) for `mode: melody`.")
    melody_offset: Union[str, float] = Field(default="0ms", description="Start-time offset between reference melody and recording.")
    pitch_unit: Union[PitchUnit, str] = Field(default=PitchUnit.SEMITONE, description="Unit of `pitch.pitch` values — 'hz' or 'semitone'.")
    mode: Union[MusicPitchCorrectionMode, str] = Field(default=MusicPitchCorrectionMode.SCALE, description="How target pitches are chosen.")
    align: Optional[Union[MusicPitchCorrectionAlignMode, str]] = Field(default=None, description="Per-note time alignment strategy for `mode: melody`; omit for no alignment.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Output sample rate; defaults to the input's rate.")
    return_frames: Union[bool, str] = Field(default=True, description="Include dense per-frame arrays in the emitted curve.")
    return_curve: Union[bool, str] = Field(default=False, description="Also emit the computed curve alongside the audio.")
    params: MusicPitchCorrectorParamsConfig = Field(default_factory=MusicPitchCorrectorParamsConfig, description="Correction algorithm tuning (strength, retune_speed, tolerances, ...).")

class CommonMusicPitchCorrectorPlanActionConfig(CommonMusicPitchCorrectorActionConfig):
    method: Literal[MusicPitchCorrectorActionMethod.PLAN]
    pitch: Union[List[List[Dict[str, Any]]], List[Dict[str, Any]], str] = Field(..., description="Pitch frames (list of `{time, pitch, confidence?}` dicts) from music-pitch-estimation or a compatible estimator.")
    key: Optional[Union[List[str], str]] = Field(default=None, description="Tonic for `mode: scale` (e.g. 'A', 'F#'). From music-analyzer key output.")
    scale: Union[List[List[int]], List[MusicPitchCorrectionScale], List[int], MusicPitchCorrectionScale, str] = Field(default=MusicPitchCorrectionScale.MAJOR, description="Scale name or pitch-class list for `mode: scale`.")
    melody: Optional[Union[List[List[Dict[str, Any]]], List[Dict[str, Any]], str]] = Field(default=None, description="Reference melody (notes list or MIDI path) for `mode: melody`.")
    melody_offset: Union[str, float] = Field(default="0ms", description="Start-time offset between reference melody and recording.")
    pitch_unit: Union[PitchUnit, str] = Field(default=PitchUnit.SEMITONE, description="Unit of `pitch.pitch` values — 'hz' or 'semitone'.")
    mode: Union[MusicPitchCorrectionMode, str] = Field(default=MusicPitchCorrectionMode.SCALE, description="How target pitches are chosen.")
    align: Optional[Union[MusicPitchCorrectionAlignMode, str]] = Field(default=None, description="Per-note time alignment strategy for `mode: melody`; omit for no alignment.")
    return_frames: Union[bool, str] = Field(default=True, description="Include dense per-frame arrays in the emitted curve.")
    params: MusicPitchCorrectorParamsConfig = Field(default_factory=MusicPitchCorrectorParamsConfig, description="Correction algorithm tuning (strength, retune_speed, tolerances, ...).")

class CommonMusicPitchCorrectorApplyActionConfig(CommonMusicPitchCorrectorActionConfig):
    method: Literal[MusicPitchCorrectorActionMethod.APPLY]
    curve: Union[List[Dict[str, Any]], Dict[str, Any], str] = Field(..., description="Correction curve from `plan`, optionally hand-edited.")
    audio: Union[str, List[str]] = Field(..., description="Vocal recording to resynthesize with corrected pitch.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Output sample rate; defaults to the input's rate.")
