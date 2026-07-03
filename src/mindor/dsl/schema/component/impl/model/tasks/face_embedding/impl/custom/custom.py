from typing import Union, Annotated
from pydantic import Field
from .impl.insightface import InsightfaceFaceEmbeddingModelComponentConfig
from .impl.facenet import FacenetFaceEmbeddingModelComponentConfig
from .impl.dlib import DlibFaceEmbeddingModelComponentConfig

CustomFaceEmbeddingModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceEmbeddingModelComponentConfig,
        FacenetFaceEmbeddingModelComponentConfig,
        DlibFaceEmbeddingModelComponentConfig,
    ],
    Field(discriminator="family")
]
