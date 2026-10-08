from pydantic import Field
from ..common import CommonMusicPitchEstimationModelActionConfig, CommonMusicPitchEstimationParamsConfig

class PestoMusicPitchEstimationParamsConfig(CommonMusicPitchEstimationParamsConfig):
    pass

class PestoMusicPitchEstimationModelActionConfig(CommonMusicPitchEstimationModelActionConfig):
    params: PestoMusicPitchEstimationParamsConfig = Field(default_factory=PestoMusicPitchEstimationParamsConfig, description="PESTO pitch estimation parameters.")
