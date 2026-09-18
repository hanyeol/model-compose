from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import VideoEmbeddingModelActionConfig
from .common import CommonVideoEmbeddingModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceVideoEmbeddingModelArchitecture(str, Enum):
    AUTO     = "auto"
    XCLIP    = "xclip"
    VIDEOMAE = "videomae"

class HuggingfaceVideoEmbeddingModelComponentConfig(CommonVideoEmbeddingModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceVideoEmbeddingModelArchitecture = Field(default=HuggingfaceVideoEmbeddingModelArchitecture.AUTO, description="Video embedding model architecture; \"auto\" infers from the model config.")
    actions: List[VideoEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this video embedding component exposes to workflows.")
