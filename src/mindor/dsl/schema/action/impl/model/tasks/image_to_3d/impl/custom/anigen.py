from typing import Union, Optional
from pydantic import Field
from ..common import CommonImageTo3DParamsConfig, CommonImageTo3DModelActionConfig

class AniGenImageTo3DParamsConfig(CommonImageTo3DParamsConfig):
    cfg_scale_ss: Union[float, str] = Field(default=7.5, description="Sparse-structure classifier-free guidance scale.")
    cfg_scale_slat: Union[float, str] = Field(default=3.0, description="Structured-latent classifier-free guidance scale.")
    ss_steps: Union[int, str] = Field(default=25, description="Sparse-structure flow-matching sampling steps.")
    slat_steps: Union[int, str] = Field(default=25, description="Structured-latent flow-matching sampling steps.")
    joints_density: Union[int, str] = Field(default=1, description="Joint density level (0-4) used by SLAT-Flow-Control; higher means more joints.")
    simplify_ratio: Union[float, str] = Field(default=0.95, description="Mesh simplification ratio applied during postprocessing.")
    fill_holes: Union[bool, str] = Field(default=True, description="Fill holes during mesh postprocessing.")
    no_smooth_skin_weights: Union[bool, str] = Field(default=False, description="Disable skin-weight smoothing.")
    smooth_skin_weights_iters: Union[int, str] = Field(default=100, description="Skin-weight smoothing iterations.")
    smooth_skin_weights_alpha: Union[float, str] = Field(default=1.0, description="Skin-weight smoothing alpha.")
    no_filter_skin_weights: Union[bool, str] = Field(default=False, description="Disable geodesic filtering of mesh skinning weights.")
    texture_size: Union[int, str] = Field(default=1024, description="Baked texture size (pixels); 0 disables texture baking.")

class AniGenImageTo3DModelActionConfig(CommonImageTo3DModelActionConfig):
    return_mesh: Union[bool, str] = Field(default=True, description="Include the rigged mesh GLB in the result.")
    return_skeleton: Union[bool, str] = Field(default=True, description="Include the skeleton visualization GLB in the result.")
    return_image: Union[bool, str] = Field(default=False, description="Include the background-removed conditioning image in the result.")
    params: AniGenImageTo3DParamsConfig = Field(default_factory=AniGenImageTo3DParamsConfig, description="AniGen image-to-3d generation parameters.")
