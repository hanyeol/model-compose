from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class DocumentLoaderDriver(str, Enum):
    DOCLING = "docling"
    PYPDF   = "pypdf"

class CommonDocumentLoaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.DOCUMENT_LOADER]
    driver: DocumentLoaderDriver = Field(..., description="Backend implementation used for document loading.")
