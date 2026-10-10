from typing import Literal, Union, List
from pydantic import Field
from mindor.dsl.schema.action import WorldMusicPitchCorrectorActionConfig
from .common import CommonMusicPitchCorrectorComponentConfig, MusicPitchCorrectorDriverType

class WorldMusicPitchCorrectorComponentConfig(CommonMusicPitchCorrectorComponentConfig):
    driver: Literal[MusicPitchCorrectorDriverType.WORLD]
    frame_period: Union[float, str] = Field(default="5ms", description="Analysis hop for WORLD (dio/harvest, cheaptrick, d4c).")
    f0_estimator: Union[Literal["dio", "harvest"], str] = Field(default="dio", description="WORLD F0 extractor used during resynthesis analysis.")
    actions: List[WorldMusicPitchCorrectorActionConfig] = Field(default_factory=list)
