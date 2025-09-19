from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
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

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(ImageToTextModelActionConfig.model_fields.keys()) - set(CommonModelComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
