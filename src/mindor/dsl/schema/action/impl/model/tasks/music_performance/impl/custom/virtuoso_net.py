from typing import Union, Literal, Optional, Annotated
from enum import Enum
from pydantic import Field
from ..common import (
    CommonMusicPerformanceParamsConfig,
    CommonMusicPerformanceModelActionConfig,
    MusicPerformanceActionMethod,
)

class VirtuosoNetComposer(str, Enum):
    BACH         = "bach"
    BALAKIREV    = "balakirev"
    BEETHOVEN    = "beethoven"
    BRAHMS       = "brahms"
    CHOPIN       = "chopin"
    DEBUSSY      = "debussy"
    GLINKA       = "glinka"
    HAYDN        = "haydn"
    LISZT        = "liszt"
    MOZART       = "mozart"
    PROKOFIEV    = "prokofiev"
    RACHMANINOFF = "rachmaninoff"
    RAVEL        = "ravel"
    SCHUBERT     = "schubert"
    SCHUMANN     = "schumann"
    SCRIABIN     = "scriabin"

class VirtuosoNetMusicPerformanceParamsConfig(CommonMusicPerformanceParamsConfig):
    qpm_primo: Optional[Union[float, str]] = Field(default=None, description="Initial tempo in QPM; defaults to the score's own tempo when unset.")
    bool_pedal: Union[bool, str] = Field(default=False, description="Threshold pedal CC64 to on/off for players that treat any non-zero value as on.")
    disklavier: Union[bool, str] = Field(default=False, description="Emit MIDI tuned for Yamaha Disklavier playback.")
    multi_instruments: Union[bool, str] = Field(default=False, description="Separate each MusicXML part into its own MIDI track.")
    tempo_clock: Union[bool, str] = Field(default=False, description="Insert a tempo clock track into the output MIDI.")
    clock_interval_in_16th: Union[int, str] = Field(default=4, description="Clock track interval in sixteenth notes; used only when `tempo_clock` is on.")
    velocity_multiplier: Union[float, str] = Field(default=1.0, description="Global velocity multiplier applied to the generated performance.")

class VirtuosoNetMusicPerformanceModelRenderActionConfig(CommonMusicPerformanceModelActionConfig):
    method: Literal[MusicPerformanceActionMethod.RENDER]
    score: str = Field(..., description="MusicXML score to render as an expressive piano performance.")
    composer: Union[VirtuosoNetComposer, str] = Field(..., description="Composer style used to condition the performance.")
    params: VirtuosoNetMusicPerformanceParamsConfig = Field(default_factory=VirtuosoNetMusicPerformanceParamsConfig, description="VirtuosoNet render parameters.")

VirtuosoNetMusicPerformanceModelActionConfig = Annotated[
    Union[
        VirtuosoNetMusicPerformanceModelRenderActionConfig,
    ],
    Field(discriminator="method")
]
