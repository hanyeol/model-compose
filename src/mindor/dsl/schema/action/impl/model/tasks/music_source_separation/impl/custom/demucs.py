from typing import Union, Optional
from pydantic import Field
from ..common import CommonMusicSourceSeparationModelActionConfig, CommonMusicSourceSeparationParamsConfig

class DemucsMusicSourceSeparationParamsConfig(CommonMusicSourceSeparationParamsConfig):
    shifts: Optional[Union[int, str]] = Field(default=None, description="Number of random shifts for equivariant stabilization; higher values improve quality but are slower.")

class DemucsMusicSourceSeparationModelActionConfig(CommonMusicSourceSeparationModelActionConfig):
    params: DemucsMusicSourceSeparationParamsConfig = Field(default_factory=DemucsMusicSourceSeparationParamsConfig, description="Demucs stem selection and separation quality parameters.")
