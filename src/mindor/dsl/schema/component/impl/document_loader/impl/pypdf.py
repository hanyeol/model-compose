from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import PypdfDocumentLoaderActionConfig
from .common import CommonDocumentLoaderComponentConfig, DocumentLoaderDriver

class PypdfDocumentLoaderComponentConfig(CommonDocumentLoaderComponentConfig):
    driver: Literal[DocumentLoaderDriver.PYPDF]
    actions: List[PypdfDocumentLoaderActionConfig] = Field(default_factory=list)
