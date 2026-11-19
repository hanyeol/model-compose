from pydantic import Field
from ...common import CommonVideoToVideoParamsConfig, CommonVideoToVideoModelActionConfig

class CommonHuggingfaceVideoToVideoParamsConfig(CommonVideoToVideoParamsConfig):
    pass

class CommonHuggingfaceVideoToVideoModelActionConfig(CommonVideoToVideoModelActionConfig):
    params: CommonHuggingfaceVideoToVideoParamsConfig = Field(default_factory=CommonHuggingfaceVideoToVideoParamsConfig, description="Sampling parameters used for video-to-video generation.")
