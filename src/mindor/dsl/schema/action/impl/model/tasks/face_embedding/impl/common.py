from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceEmbeddingParamsConfig(BaseModel):
    face_detection: bool = Field(default=True, description="Whether to perform face detection before embedding.")
    alignment: bool = Field(default=True, description="Whether to align faces before embedding.")
    normalize_embeddings: bool = Field(default=True, description="Whether to L2-normalize output embeddings.")

class CommonFaceEmbeddingModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image for face embedding extraction.")
    batch_size: Union[int, str] = Field(default=1, description="Images per batch.")
    params: CommonFaceEmbeddingParamsConfig = Field(default_factory=CommonFaceEmbeddingParamsConfig, description="Face embedding parameters.")
