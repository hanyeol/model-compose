from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeAudioProcessorActionConfig
from .common import CommonAudioProcessorComponentConfig, AudioProcessorDriverType

class NativeAudioProcessorComponentConfig(CommonAudioProcessorComponentConfig):
    driver: Literal[AudioProcessorDriverType.NATIVE]
    actions: List[NativeAudioProcessorActionConfig] = Field(default_factory=list)
