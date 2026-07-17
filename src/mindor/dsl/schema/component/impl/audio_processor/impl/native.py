from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioProcessorActionConfig
from .common import CommonAudioProcessorComponentConfig, AudioProcessorDriver

class NativeAudioProcessorComponentConfig(CommonAudioProcessorComponentConfig):
    driver: Literal[AudioProcessorDriver.NATIVE]
    actions: List[AudioProcessorActionConfig] = Field(default_factory=list)
