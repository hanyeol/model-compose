from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from ....common import ModelDriver

class MidiDdspMusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicGenerationModelFamily.MIDI_DDSP]
    expression_generator_weights: Optional[str] = Field(default=None, description="Path to the expression generator checkpoint; defaults to <model>/expression_generator/5000 when unset.")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this MIDI-DDSP component exposes to workflows.")
