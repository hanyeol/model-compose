from enum import Enum
from typing import Union, Optional
from pydantic import BaseModel, Field
from ..common import CommonImageTo3DParamsConfig, CommonImageTo3DModelActionConfig

class WorldMirrorSkyMaskSource(str, Enum):
    AUTO  = "auto"
    MODEL = "model"
    ONNX  = "onnx"

class WorldMirrorImageTo3DParamsConfig(CommonImageTo3DParamsConfig):
    target_size: Union[int, str] = Field(default=952, description="Maximum inference resolution (longest edge); images are resized + center-cropped to a multiple of 14.")
    apply_sky_mask: Union[bool, str] = Field(default=True, description="Filter sky regions out of point clouds and Gaussians.")
    apply_edge_mask: Union[bool, str] = Field(default=True, description="Filter points near depth/normal discontinuities.")
    apply_confidence_mask: Union[bool, str] = Field(default=False, description="Filter the bottom-percentile of points by prediction confidence.")
    sky_mask_source: Union[WorldMirrorSkyMaskSource, str] = Field(default=WorldMirrorSkyMaskSource.AUTO, description="Sky mask source: `auto` fuses ONNX + model, `model` uses only the model, `onnx` uses only external segmentation.")
    model_sky_threshold: Union[float, str] = Field(default=0.45, description="Threshold for model-based sky detection.")
    confidence_percentile: Union[float, str] = Field(default=10.0, description="Bottom percentile removed when `apply_confidence_mask` is enabled.")
    edge_normal_threshold: Union[float, str] = Field(default=1.0, description="Normal-edge detection tolerance.")
    edge_depth_threshold: Union[float, str] = Field(default=0.03, description="Depth-edge detection relative tolerance.")
    compress_pts: Union[bool, str] = Field(default=True, description="Compress the depth-derived point cloud via voxel merging + subsampling.")
    compress_pts_max_points: Union[int, str] = Field(default=2_000_000, description="Maximum number of points after point-cloud compression.")
    compress_pts_voxel_size: Union[float, str] = Field(default=0.002, description="Voxel size used when merging points.")
    compress_gs_max_points: Union[int, str] = Field(default=5_000_000, description="Maximum number of Gaussians after voxel pruning.")
    max_resolution: Union[int, str] = Field(default=1920, description="Maximum resolution for any saved image outputs (depth/normal PNGs).")

class WorldMirrorPriorsConfig(BaseModel):
    cameras: Optional[str] = Field(default=None, description="Path to a camera priors JSON file (same schema as WorldMirror's `camera_params.json` output).")
    depths: Optional[str] = Field(default=None, description="Path to a directory of per-view depth maps (.npy/.exr/.png) whose filenames match the input images.")

class WorldMirrorImageTo3DModelActionConfig(CommonImageTo3DModelActionConfig):
    priors: WorldMirrorPriorsConfig = Field(default_factory=WorldMirrorPriorsConfig, description="Optional geometric priors injected as conditioning inputs.")
    return_gaussians: Union[bool, str] = Field(default=True, description="Include the 3D Gaussian Splatting `.ply` in the result.")
    return_points: Union[bool, str] = Field(default=True, description="Include the depth-derived point cloud `.ply` in the result.")
    return_cameras: Union[bool, str] = Field(default=True, description="Include camera extrinsics and intrinsics as a JSON dict in the result.")
    return_depth: Union[bool, str] = Field(default=False, description="Include per-view depth map images in the result.")
    return_normal: Union[bool, str] = Field(default=False, description="Include per-view surface normal map images in the result.")
    params: WorldMirrorImageTo3DParamsConfig = Field(default_factory=WorldMirrorImageTo3DParamsConfig, description="WorldMirror inference parameters.")
