from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceSwapParamsConfig(BaseModel):
    pass

class CommonFaceSwapModelActionConfig(CommonModelActionConfig):
    source_image: str = Field(..., description="Source image supplying the face identity that is transferred.")
    target_image: Union[str, List[str]] = Field(..., description="Target image or images whose faces are replaced by the source identity.")
    swap_all_faces: Union[bool, str] = Field(default=True, description="Whether every detected target face is swapped.")
    face_index: Union[int, str] = Field(default=0, description="Index of the target face swapped when `swap_all_faces` is false.")
    batch_size: Union[int, str] = Field(default=1, description="Number of target images processed per batch.")
    params: CommonFaceSwapParamsConfig = Field(default_factory=CommonFaceSwapParamsConfig, description="Backend-specific face swap parameters.")
