from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import PymupdfDocumentLoaderActionConfig
from .common import CommonDocumentLoaderComponentConfig, DocumentLoaderDriverType

class PymupdfDocumentLoaderComponentConfig(CommonDocumentLoaderComponentConfig):
    driver: Literal[DocumentLoaderDriverType.PYMUPDF]
    actions: List[PymupdfDocumentLoaderActionConfig] = Field(default_factory=list)
