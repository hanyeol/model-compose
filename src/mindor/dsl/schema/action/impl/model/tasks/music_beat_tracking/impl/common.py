from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonMusicBeatTrackingParamsConfig(BaseModel):
    pass

class CommonMusicBeatTrackingModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to track beats in, or a list of audios.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    return_metadata: Union[bool, str] = Field(default=True, description="Whether processing metadata (duration, ...) is included in the result.")
    params: CommonMusicBeatTrackingParamsConfig = Field(default_factory=CommonMusicBeatTrackingParamsConfig, description="Beat tracking parameters applied to the model.")
