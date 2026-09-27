from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HuggingfaceSpeakerDiarizationModelActionConfig
from .common import CommonSpeakerDiarizationModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceSpeakerDiarizationModelComponentConfig(CommonSpeakerDiarizationModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    actions: List[HuggingfaceSpeakerDiarizationModelActionConfig] = Field(default_factory=list, description="Actions this speaker diarization component exposes to workflows.")
