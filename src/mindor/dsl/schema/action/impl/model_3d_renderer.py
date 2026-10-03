from typing import Union, Optional, Literal, List
from pydantic import BaseModel, Field
from mindor.dsl.schema.common.color import Color
from .common import CommonActionConfig

class Model3DRendererCameraConfig(BaseModel):
    yaw: Union[float, str] = Field(default=30.0, description="Camera yaw in degrees around the model's up axis.")
    pitch: Union[float, str] = Field(default=20.0, description="Camera pitch in degrees above the horizon.")
    roll: Union[float, str] = Field(default=0.0, description="Camera roll in degrees.")
    distance: Optional[Union[float, str]] = Field(default=None, description="Camera distance; auto-fit from the model's bounding sphere if omitted.")
    fov: Union[float, str] = Field(default=45.0, description="Vertical field of view in degrees.")
    up: Optional[Union[Literal["y", "z"], str]] = Field(default="y", description="Up axis of the input model.")

class Model3DRendererLightingConfig(BaseModel):
    preset: Optional[Union[Literal[ "studio", "flat", "outdoor" ], str]] = Field(default="studio", description="Lighting preset.")
    ambient: Union[float, str] = Field(default=0.3, description="Hemisphere ambient intensity (0-1).")
    directional: Union[float, str] = Field(default=1.0, description="Key directional light intensity.")
    exposure: Union[float, str] = Field(default=1.0, description="Final exposure multiplier applied before tone mapping.")
    follow_camera: Union[bool, str] = Field(default=True, description="If true the rig rotates with the camera; if false the rig stays fixed in world space.")

class Model3DRendererActionConfig(CommonActionConfig):
    model_3d: Union[str, List[str]] = Field(..., description="3D model source or list of sources to render.")
    camera: Optional[Union[Model3DRendererCameraConfig, List[Model3DRendererCameraConfig], str]] = Field(default=None, description="Camera placement; a single object renders one view, a list renders one per entry.")
    lighting: Optional[Union[Model3DRendererLightingConfig, List[Model3DRendererLightingConfig], str]] = Field(default=None, description="Scene lighting; a single object applies to all views, a list pairs one per entry.")
    format: Union[Literal[ "png", "jpeg" ], str] = Field(default="png", description="Output image format.")
    width: Union[int, str] = Field(default=512, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=512, description="Output image height in pixels.")
    fit: Union[Literal[ "contain", "cover", "none" ], str] = Field(default="contain", description="How to fit the model in frame.")
    background: Optional[Union[Color, str]] = Field(default=None, description="Background color as a hex string or RGBA tuple; None yields a transparent canvas.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input models processed per batch.")
