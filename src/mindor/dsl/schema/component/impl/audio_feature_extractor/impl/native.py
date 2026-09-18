from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from .common import CommonAudioFeatureExtractorComponentConfig, AudioFeatureExtractorDriverType

class NativeAudioFeatureExtractorComponentConfig(CommonAudioFeatureExtractorComponentConfig):
    driver: Literal[AudioFeatureExtractorDriverType.NATIVE]
    actions: List[AudioFeatureExtractorActionConfig] = Field(default_factory=list)
