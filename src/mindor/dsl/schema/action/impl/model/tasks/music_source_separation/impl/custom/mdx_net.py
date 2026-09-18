from pydantic import Field
from ..common import CommonMusicSourceSeparationModelActionConfig, CommonMusicSourceSeparationParamsConfig

class MdxNetMusicSourceSeparationParamsConfig(CommonMusicSourceSeparationParamsConfig):
    pass

class MdxNetMusicSourceSeparationModelActionConfig(CommonMusicSourceSeparationModelActionConfig):
    params: MdxNetMusicSourceSeparationParamsConfig = Field(default_factory=MdxNetMusicSourceSeparationParamsConfig, description="MDX-Net stem selection and separation quality parameters.")
