from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageEmbeddingModelActionConfig
from .common import CommonImageEmbeddingModelComponentConfig
from ...common import ModelDriver

class HuggingfaceImageEmbeddingModelArchitecture(str, Enum):
    AUTO   = "auto"
    CLIP   = "clip"
    SIGLIP = "siglip"
    DINOV2 = "dinov2"

class HuggingfaceImageEmbeddingModelComponentConfig(CommonImageEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceImageEmbeddingModelArchitecture = Field(default=HuggingfaceImageEmbeddingModelArchitecture.AUTO, description="How to load and run the image embedding model.")
    actions: List[ImageEmbeddingModelActionConfig] = Field(default_factory=list)
