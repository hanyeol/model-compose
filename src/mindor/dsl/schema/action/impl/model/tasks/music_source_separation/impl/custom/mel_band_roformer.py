from typing import Union, Optional
from pydantic import Field
from ..common import CommonMusicSourceSeparationModelActionConfig, CommonMusicSourceSeparationParamsConfig

class MelBandRoFormerMusicSourceSeparationParamsConfig(CommonMusicSourceSeparationParamsConfig):
    chunk_duration: Optional[Union[float, str]] = Field(default=None, description="Chunk length in seconds fed to the transformer; defaults to ~8 seconds at the model's sample rate.")

class MelBandRoFormerMusicSourceSeparationModelActionConfig(CommonMusicSourceSeparationModelActionConfig):
    params: MelBandRoFormerMusicSourceSeparationParamsConfig = Field(default_factory=MelBandRoFormerMusicSourceSeparationParamsConfig, description="Mel-Band RoFormer stem selection and separation quality parameters.")
