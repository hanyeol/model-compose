from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver

class HuggingfaceTextEmbeddingModelArchitecture(str, Enum):
    AUTO  = "auto"
    BERT  = "bert"
    SBERT = "sbert"

class HuggingfaceTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceTextEmbeddingModelArchitecture = Field(default=HuggingfaceTextEmbeddingModelArchitecture.AUTO, description="How to load and run the embedding model.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
