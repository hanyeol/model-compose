from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import SpeakerDiarizationModelActionConfig
from ...common import CommonSpeakerDiarizationModelComponentConfig
from .common import SpeakerDiarizationModelFamily
from .....common import ModelDriver, ModelConfig

class PyannoteSpeakerDiarizationModelComponentConfig(CommonSpeakerDiarizationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeakerDiarizationModelFamily.PYANNOTE]
    model: Optional[Union[str, ModelConfig]] = Field(default=None, description="pyannote.audio pipeline id (defaults to 'pyannote/speaker-diarization-3.1'). Requires a HuggingFace access token accepted for the gated model.")
    actions: List[SpeakerDiarizationModelActionConfig] = Field(default_factory=list)
