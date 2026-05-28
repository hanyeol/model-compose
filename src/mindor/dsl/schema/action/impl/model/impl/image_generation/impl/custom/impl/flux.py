from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig

class FluxImageGenerationParamsConfig(BaseModel):
    pass

class FluxImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: FluxImageGenerationParamsConfig = Field(..., description="Image generation configuration parameters.")
