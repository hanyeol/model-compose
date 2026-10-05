from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonLipSyncParamsConfig(BaseModel):
    frame_rate: Optional[Union[int, float, str]] = Field(default=None, description="Output video frame rate; floats and NTSC rationals like 29.97 are accepted. Defaults to the source video's frame rate when unset.")

class CommonLipSyncModelActionConfig(CommonModelActionConfig):
    video: Union[str, List[str]] = Field(..., description="Input face video or list of videos whose lips are re-synced.")
    audio: Union[str, List[str]] = Field(..., description="Input audio or list of audios driving the new lip motion.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonLipSyncParamsConfig = Field(default_factory=CommonLipSyncParamsConfig, description="Generation parameters applied to the lip-synced video.")
