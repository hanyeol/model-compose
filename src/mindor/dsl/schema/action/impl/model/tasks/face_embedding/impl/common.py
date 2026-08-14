from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceEmbeddingParamsConfig(BaseModel):
    face_detection: bool = Field(default=True, description="Whether face detection is run before embedding.")
    alignment: bool = Field(default=True, description="Whether detected faces are aligned before embedding.")
    normalize_embeddings: bool = Field(default=True, description="Whether output embeddings are L2-normalized.")
    min_face_size: int = Field(default=0, description="Minimum face bounding box size in pixels; 0 disables the filter.")

class CommonFaceEmbeddingModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to extract face embeddings from.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonFaceEmbeddingParamsConfig = Field(default_factory=CommonFaceEmbeddingParamsConfig, description="Detection, alignment, and normalization parameters for face embedding.")
