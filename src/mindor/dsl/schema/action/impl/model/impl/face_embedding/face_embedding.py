from typing import Union
from .impl import *

FaceEmbeddingModelActionConfig = Union[
    InsightfaceFaceEmbeddingModelActionConfig,
    FacenetFaceEmbeddingModelActionConfig,
    DlibFaceEmbeddingModelActionConfig
]
