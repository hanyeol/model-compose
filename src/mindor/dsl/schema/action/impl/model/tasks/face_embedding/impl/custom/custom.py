from typing import Union
from .insightface import InsightfaceFaceEmbeddingModelActionConfig
from .facenet import FacenetFaceEmbeddingModelActionConfig
from .dlib import DlibFaceEmbeddingModelActionConfig

CustomFaceEmbeddingModelActionConfig = Union[
    InsightfaceFaceEmbeddingModelActionConfig,
    FacenetFaceEmbeddingModelActionConfig,
    DlibFaceEmbeddingModelActionConfig,
]
