from typing import Union, Annotated
from pydantic import Field
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
