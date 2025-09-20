from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class CommonFaceEmbeddingModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image for face embedding extraction.")
    face_detection: bool = Field(default=True, description="Whether to perform face detection before embedding.")
    alignment: bool = Field(default=True, description="Whether to align faces before embedding.")
    normalize_embeddings: bool = Field(default=True, description="Whether to L2-normalize the output embeddings.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")
