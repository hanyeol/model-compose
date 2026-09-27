from __future__ import annotations

from typing import Union, Optional
from pydantic import Field, model_validator
from ..common import CommonVideoToVideoParamsConfig, CommonVideoToVideoModelActionConfig

class WanVideoToVideoParamsConfig(CommonVideoToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=20, description="Number of diffusion sampling steps.")
    guidance_scale: Union[float, str] = Field(default=1.0, description="Classifier-free guidance scale used for expression control.")
    shift: Union[float, str] = Field(default=5.0, description="Flow-matching timestep shift applied to the scheduler.")
    clip_len: Union[int, str] = Field(default=77, description="Frames generated per clip; must satisfy 4n+1.")
    refert_num: Union[int, str] = Field(default=1, description="Number of frames used as temporal guidance between clips; 1 or 5.")
    preprocess_fps: Union[int, str] = Field(default=30, description="Target fps used when sampling the driving video during preprocessing; -1 keeps the video's native fps.")
    resolution_width: Union[int, str] = Field(default=1280, description="Preprocessing resolution width; the driving video is resized to preserve aspect ratio within width * height area.")
    resolution_height: Union[int, str] = Field(default=720, description="Preprocessing resolution height; paired with `resolution_width` to define the target area.")
    retarget_flag: Union[bool, str] = Field(default=False, description="Enable pose retargeting during preprocessing.")
    use_flux: Union[bool, str] = Field(default=False, description="Use FLUX.1-Kontext image editing during pose retargeting; requires `retarget_flag` and the component's `flux_kontext_model`.")
    replace_flag: Union[bool, str] = Field(default=False, description="Enable character replacement mode; requires the component's `sam2_model` to be configured.")
    mask_iterations: Union[int, str] = Field(default=3, description="Mask dilation iterations used in replacement mode.")
    mask_kernel_size: Union[int, str] = Field(default=7, description="Mask dilation kernel size used in replacement mode.")
    mask_w_len: Union[int, str] = Field(default=1, description="Grid subdivisions along the width axis used to refine the replacement mask contour.")
    mask_h_len: Union[int, str] = Field(default=1, description="Grid subdivisions along the height axis used to refine the replacement mask contour.")

class WanVideoToVideoModelActionConfig(CommonVideoToVideoModelActionConfig):
    params: WanVideoToVideoParamsConfig = Field(default_factory=WanVideoToVideoParamsConfig, description="Wan-Animate video-to-video generation parameters.")

    @model_validator(mode="after")
    def validate_reference_image(self) -> "WanVideoToVideoModelActionConfig":
        # Wan-Animate needs a reference character image alongside the driving clip.
        # `video XOR frames` is already enforced by the base class validator.
        if self.reference_image is None:
            raise ValueError("Wan-Animate requires `reference_image` (target character) to be set.")
        return self
