from typing import Union, List
from pydantic import Field
from ..common import CommonHumanMeshRecoveryParamsConfig, CommonHumanMeshRecoveryModelActionConfig

class HMR2HumanMeshRecoveryParamsConfig(CommonHumanMeshRecoveryParamsConfig):
    rescale_factor: Union[float, str] = Field(default=2.0, description="Bounding-box rescale factor applied around each detected person before cropping to the model's input.")

class HMR2HumanMeshRecoveryModelActionConfig(CommonHumanMeshRecoveryModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to recover body meshes from.")
    max_person_count: Union[int, str] = Field(default=1, description="Maximum number of people recovered per image.")
    params: HMR2HumanMeshRecoveryParamsConfig = Field(default_factory=HMR2HumanMeshRecoveryParamsConfig, description="HMR2 recovery parameters.")
