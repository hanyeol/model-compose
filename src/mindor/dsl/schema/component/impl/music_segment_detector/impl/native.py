from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeMusicSegmentDetectorActionConfig
from .common import CommonMusicSegmentDetectorComponentConfig, MusicSegmentDetectorDriverType

class NativeMusicSegmentDetectorComponentConfig(CommonMusicSegmentDetectorComponentConfig):
    driver: Literal[MusicSegmentDetectorDriverType.NATIVE]
    actions: List[NativeMusicSegmentDetectorActionConfig] = Field(default_factory=list)
