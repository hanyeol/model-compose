from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class DocumentLoaderDriverType(str, Enum):
    DOCLING = "docling"
    PYPDF   = "pypdf"

class CommonDocumentLoaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.DOCUMENT_LOADER]
    driver: DocumentLoaderDriverType = Field(..., description="Backend implementation used for document loading.")
