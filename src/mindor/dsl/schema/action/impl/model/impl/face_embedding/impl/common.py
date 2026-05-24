from typing import Union, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonFaceEmbeddingModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image for face embedding extraction.")
    face_detection: bool = Field(default=True, description="Whether to perform face detection before embedding.")
    alignment: bool = Field(default=True, description="Whether to align faces before embedding.")
    normalize_embeddings: bool = Field(default=True, description="Whether to L2-normalize the output embeddings.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")
