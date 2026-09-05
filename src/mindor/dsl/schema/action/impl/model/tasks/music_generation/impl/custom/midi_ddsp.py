from typing import Union, Literal, Optional, List, Annotated
from enum import Enum
from pydantic import Field
from ..common import (
    CommonMusicGenerationParamsConfig,
    CommonMusicGenerationModelActionConfig,
    MusicGenerationActionMethod,
)

class MidiDdspInstrument(str, Enum):
    VIOLIN      = "violin"
    VIOLA       = "viola"
    CELLO       = "cello"
    DOUBLE_BASS = "double-bass"
    FLUTE       = "flute"
    OBOE        = "oboe"
    CLARINET    = "clarinet"
    SAXOPHONE   = "saxophone"
    BASSOON     = "bassoon"
    TRUMPET     = "trumpet"
    HORN        = "horn"
    TROMBONE    = "trombone"
    TUBA        = "tuba"

class MidiDdspMusicGenerationParamsConfig(CommonMusicGenerationParamsConfig):
    pitch_offset: Union[int, str] = Field(default=0, description="Semitones to transpose the input MIDI before synthesis.")
    speed_rate: Union[float, str] = Field(default=1.0, description="Playback speed multiplier applied to the MIDI sequence.")
    vibrato_extent: Optional[Union[float, str]] = Field(default=None, description="Global override for the vibrato extent expression control (0.0-1.0).")
    vibrato_attack: Optional[Union[float, str]] = Field(default=None, description="Global override for the vibrato attack expression control (0.0-1.0).")
    brightness: Optional[Union[float, str]] = Field(default=None, description="Global override for the brightness expression control (0.0-1.0).")
    attack_noise: Optional[Union[float, str]] = Field(default=None, description="Global override for the attack noise expression control (0.0-1.0).")
    volume: Optional[Union[float, str]] = Field(default=None, description="Global override for the volume expression control (0.0-1.0).")
    volume_fluctuation: Optional[Union[float, str]] = Field(default=None, description="Global override for the volume fluctuation expression control (0.0-1.0).")

class CommonMidiDdspMusicGenerationModelActionConfig(CommonMusicGenerationModelActionConfig):
    params: MidiDdspMusicGenerationParamsConfig = Field(default_factory=MidiDdspMusicGenerationParamsConfig, description="MIDI-DDSP synthesis parameters and expression overrides.")

class MidiDdspMusicGenerationModelGenerateActionConfig(CommonMidiDdspMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.GENERATE]
    midi: str = Field(..., description="Monophonic MIDI to synthesize.")
    instrument: MidiDdspInstrument = Field(..., description="Instrument voice used to synthesize every track in the MIDI file.")

MidiDdspMusicGenerationModelActionConfig = Annotated[
    Union[
        MidiDdspMusicGenerationModelGenerateActionConfig,
    ],
    Field(discriminator="method")
]
