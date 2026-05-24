from typing import Union, Annotated
from enum import Enum
from pydantic import Field

class CustomFaceEmbeddingModelFamily(str, Enum):
    INSIGHTFACE = "insightface"
    FACENET     = "facenet"
    DLIB        = "dlib"

from .insightface import InsightfaceFaceEmbeddingModelComponentConfig
from .facenet import FacenetFaceEmbeddingModelComponentConfig
from .dlib import DlibFaceEmbeddingModelComponentConfig

CustomFaceEmbeddingModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceEmbeddingModelComponentConfig,
        FacenetFaceEmbeddingModelComponentConfig,
        DlibFaceEmbeddingModelComponentConfig,
    ],
    Field(discriminator="family")
]
