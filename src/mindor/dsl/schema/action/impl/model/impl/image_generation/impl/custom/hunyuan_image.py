from pydantic import BaseModel, Field
from ..common import CommonImageGenerationModelActionConfig

class HunyuanImageGenerationParamsConfig(BaseModel):
    pass

class HunyuanImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: HunyuanImageGenerationParamsConfig = Field(..., description="Image generation configuration parameters.")
