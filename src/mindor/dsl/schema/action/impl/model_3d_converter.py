from typing import Union, Optional, List
from pydantic import Field
from .common import CommonActionConfig

class Model3DConverterActionConfig(CommonActionConfig):
    model_3d: Union[str, List[str]] = Field(..., description="3D model source or list of sources to convert.")
    format: Optional[str] = Field(default=None, description="Output 3D file format (e.g., glb, gltf, obj, stl, ply).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input models processed per batch.")
