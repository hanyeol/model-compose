from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class Model3DLoaderOutputFormat(str, Enum):
    GLB  = "glb"
    GLTF = "gltf"
    OBJ  = "obj"
    PLY  = "ply"
    FBX  = "fbx"
    STL  = "stl"

class CommonModel3DLoaderActionConfig(CommonActionConfig):
    source: Union[str, List[str]] = Field(..., description="3D model source as path, URL, upload stream, or raw bytes.")
    format: Union[Model3DLoaderOutputFormat, str] = Field(default=Model3DLoaderOutputFormat.GLB, description="Output format emitted into the pipeline.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of sources processed per batch.")
