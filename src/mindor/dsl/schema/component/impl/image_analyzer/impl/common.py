from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class ImageAnalyzerDriver(str, Enum):
    NATIVE = "native"

class CommonImageAnalyzerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_ANALYZER]
    driver: ImageAnalyzerDriver = Field(..., description="Backend implementation used for image analysis.")
