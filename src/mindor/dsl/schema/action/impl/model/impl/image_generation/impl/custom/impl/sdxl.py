from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig

class SdxlImageGenerationParamsConfig(BaseModel):
    pass

class SdxlImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: SdxlImageGenerationParamsConfig = Field(..., description="Image generation configuration parameters.")
