from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import PypdfDocumentLoaderActionConfig
from .common import CommonDocumentLoaderComponentConfig, DocumentLoaderDriverType

class PypdfDocumentLoaderComponentConfig(CommonDocumentLoaderComponentConfig):
    driver: Literal[DocumentLoaderDriverType.PYPDF]
    actions: List[PypdfDocumentLoaderActionConfig] = Field(default_factory=list)
