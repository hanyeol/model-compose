from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonFaceSwapModelActionConfig(CommonModelActionConfig):
    source_image: str = Field(..., description="Source image providing the face identity to transfer.")
    target_image: Union[str, List[str]] = Field(..., description="Target image(s) whose faces will be replaced by the source identity.")
    swap_all_faces: Union[bool, str] = Field(default=True, description="Swap every detected target face.")
    face_index: Union[int, str] = Field(default=0, description="Index of the target face to swap.")
    batch_size: Union[int, str] = Field(default=1, description="Target images per batch.")
