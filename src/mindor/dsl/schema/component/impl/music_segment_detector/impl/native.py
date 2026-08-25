from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicSegmentDetectorActionConfig
from .common import CommonMusicSegmentDetectorComponentConfig, MusicSegmentDetectorDriver

class NativeMusicSegmentDetectorComponentConfig(CommonMusicSegmentDetectorComponentConfig):
    driver: Literal[MusicSegmentDetectorDriver.NATIVE]
    actions: List[MusicSegmentDetectorActionConfig] = Field(default_factory=list)
