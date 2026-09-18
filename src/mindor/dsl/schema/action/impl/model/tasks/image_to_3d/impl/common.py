from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonImageTo3DParamsConfig(BaseModel):
    mesh_scale: Union[float, str] = Field(default=1.0, description="Target mesh scale used for camera-distance computation.")
    image_resolution: Union[int, str] = Field(default=512, description="Working image resolution used during camera estimation.")

class CommonImageTo3DModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images used as the sole conditioning input.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonImageTo3DParamsConfig = Field(default_factory=CommonImageTo3DParamsConfig, description="Shared image-to-3d generation parameters.")
