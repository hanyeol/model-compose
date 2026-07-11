from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonFaceSwapModelActionConfig(CommonModelActionConfig):
    source_image: str = Field(..., description="Source image providing the face identity to transfer.")
    target_image: Union[str, List[str]] = Field(..., description="Target image(s) whose faces will be replaced by the source identity.")
    swap_all_faces: Union[bool, str] = Field(default=True, description="Whether to swap every detected face in the target. If false, only the face at 'face_index' is replaced.")
    face_index: Union[int, str] = Field(default=0, description="Index of the target face to swap when 'swap_all_faces' is false. Faces are ordered by detection score (highest first).")
    batch_size: Union[int, str] = Field(default=1, description="Number of target images to process in a single batch.")
