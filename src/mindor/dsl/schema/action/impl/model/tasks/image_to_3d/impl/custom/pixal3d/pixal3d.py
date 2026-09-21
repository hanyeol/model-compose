from typing import Union, Optional
from pydantic import Field
from ...common import CommonImageTo3DModelActionConfig
from .common import CommonPixal3DImageTo3DParamsConfig

class Pixal3DImageTo3DParamsConfig(CommonPixal3DImageTo3DParamsConfig):
    manual_fov: Optional[Union[float, str]] = Field(default=None, description="Manual camera horizontal FOV in radians; unset triggers MoGe-based auto-estimation.")
    extend_pixel: Union[int, str] = Field(default=0, description="Padding pixels applied when computing camera distance from FOV.")

class Pixal3DImageTo3DModelActionConfig(CommonImageTo3DModelActionConfig):
    params: Pixal3DImageTo3DParamsConfig = Field(default_factory=Pixal3DImageTo3DParamsConfig, description="Pixal3D image-to-3d generation parameters.")
