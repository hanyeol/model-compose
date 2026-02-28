from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class ImageToTextModelArchitecture(str, Enum):
    BLIP       = "blip"
    BLIP2      = "blip2"
    GIT        = "git"
    PIX2STRUCT = "pix2struct"
    DONUT      = "donut"
    KOSMOS2    = "kosmos2"

class ImageToTextModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_TO_TEXT]
    architecture: ImageToTextModelArchitecture = Field(..., description="Model architecture.")
    actions: List[ImageToTextModelActionConfig] = Field(default_factory=list)
