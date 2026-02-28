from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ImageProcessorActionConfig
from .common import ComponentType, CommonComponentConfig

class ImageProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_PROCESSOR]
    actions: List[ImageProcessorActionConfig] = Field(default_factory=list)
