from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonImageGenerationModelActionConfig

class FluxImageGenerationParamsConfig(BaseModel):
    pass

class FluxImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: FluxImageGenerationParamsConfig = Field(..., description="Image generation configuration parameters.")
