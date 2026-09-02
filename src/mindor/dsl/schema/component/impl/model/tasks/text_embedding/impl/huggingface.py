from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver

class HuggingfaceTextEmbeddingModelArchitecture(str, Enum):
    AUTO   = "auto"
    BERT   = "bert"
    SBERT  = "sbert"
    CLIP   = "clip"
    SIGLIP = "siglip"
    XCLIP  = "xclip"

class HuggingfaceTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceTextEmbeddingModelArchitecture = Field(default=HuggingfaceTextEmbeddingModelArchitecture.AUTO, description="Embedding model architecture; \"auto\" infers from the model config.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this text embedding component exposes to workflows.")
