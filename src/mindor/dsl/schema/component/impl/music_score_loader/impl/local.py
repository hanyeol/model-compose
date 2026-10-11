from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import LocalMusicScoreLoaderActionConfig
from .common import CommonMusicScoreLoaderComponentConfig, MusicScoreLoaderDriverType

class LocalMusicScoreLoaderComponentConfig(CommonMusicScoreLoaderComponentConfig):
    driver: Literal[MusicScoreLoaderDriverType.LOCAL]
    actions: List[LocalMusicScoreLoaderActionConfig] = Field(default_factory=list)
