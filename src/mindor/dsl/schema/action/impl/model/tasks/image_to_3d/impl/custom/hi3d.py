from typing import Union
from pydantic import Field
from ..common import CommonImageTo3DParamsConfig, CommonImageTo3DModelActionConfig

class Hi3DImageTo3DParamsConfig(CommonImageTo3DParamsConfig):
    resolution: Union[int, str] = Field(default=1024, description="Sparse extraction-grid resolution used during refinement.")
    num_inference_steps: Union[int, str] = Field(default=25, description="Number of flow-matching inference steps for refinement.")

class Hi3DImageTo3DModelActionConfig(CommonImageTo3DModelActionConfig):
    mesh: str = Field(..., description="Input mesh (any trimesh-readable format) to be refined; produced upstream by another image-to-3d component.")
    params: Hi3DImageTo3DParamsConfig = Field(default_factory=Hi3DImageTo3DParamsConfig, description="Hi3D refinement parameters.")
