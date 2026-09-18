from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class ImageDrawingDriverType(str, Enum):
    NATIVE = "native"

class CommonImageDrawingComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_DRAWING]
    driver: ImageDrawingDriverType = Field(..., description="Backend implementation used for image drawing.")
