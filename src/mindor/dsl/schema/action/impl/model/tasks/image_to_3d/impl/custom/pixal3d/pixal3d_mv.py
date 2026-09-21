from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonImageTo3DModelActionConfig
from .common import CommonPixal3DImageTo3DParamsConfig

class Pixal3DMultiViewImageTo3DParamsConfig(CommonPixal3DImageTo3DParamsConfig):
    pass

class Pixal3DMultiViewImageTo3DModelActionConfig(CommonImageTo3DModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Posed view images; index 0 is the canonical front view. Length must match transform_matrix.")
    transform_matrix: Union[str, List[Union[str, List[List[float]]]]] = Field(..., description="4x4 camera-to-world matrices (NeRF/Blender convention: Z-up world, camera looks -Z with +Y up); parallel to image.")
    camera_angle_x: Optional[Union[float, str, List[Union[float, str]]]] = Field(default=None, description="Horizontal FOV in radians; scalar shared across views or list per view.")
    mesh_scale: Union[float, str] = Field(default=1.0, description="Global mesh scale applied to camera-distance normalization.")
    params: Pixal3DMultiViewImageTo3DParamsConfig = Field(default_factory=Pixal3DMultiViewImageTo3DParamsConfig, description="Pixal3D multi-view image-to-3d generation parameters.")
