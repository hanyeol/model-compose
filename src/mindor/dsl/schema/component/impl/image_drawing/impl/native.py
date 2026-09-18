from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ImageDrawingActionConfig
from .common import CommonImageDrawingComponentConfig, ImageDrawingDriverType

class NativeImageDrawingComponentConfig(CommonImageDrawingComponentConfig):
    driver: Literal[ImageDrawingDriverType.NATIVE]
    actions: List[ImageDrawingActionConfig] = Field(default_factory=list)
