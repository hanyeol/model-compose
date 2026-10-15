from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VerovioMusicScoreRendererActionConfig
from .common import CommonMusicScoreRendererComponentConfig, MusicScoreRendererDriverType

class VerovioMusicScoreRendererComponentConfig(CommonMusicScoreRendererComponentConfig):
    driver: Literal[MusicScoreRendererDriverType.VEROVIO]
    actions: List[VerovioMusicScoreRendererActionConfig] = Field(default_factory=list)
