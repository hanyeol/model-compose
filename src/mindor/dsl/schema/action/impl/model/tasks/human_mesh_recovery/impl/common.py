from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonHumanMeshRecoveryParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum confidence a returned detection must reach.")

class CommonHumanMeshRecoveryModelActionConfig(CommonModelActionConfig):
    return_joints_3d: Union[bool, str] = Field(default=True, description="Whether 3D joint positions (meters, root-centered) are included in the result.")
    return_joints_2d: Union[bool, str] = Field(default=False, description="Whether 2D projected joint positions are included in the result.")
    return_vertices: Union[bool, str] = Field(default=False, description="Whether raw mesh vertices are included in the result.")
    return_mesh: Union[bool, str] = Field(default=False, description="Whether a posed mesh file (GLB) is included in the result.")
    return_camera: Union[bool, str] = Field(default=False, description="Whether estimated camera parameters (focal length, principal point) are included in the result.")
    return_metadata: Union[bool, str] = Field(default=True, description="Whether the body-model parameters (shape, pose, translation) and other recovery metadata are included in the result.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonHumanMeshRecoveryParamsConfig = Field(default_factory=CommonHumanMeshRecoveryParamsConfig, description="Shared human-mesh-recovery parameters.")
