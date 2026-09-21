from typing import Union
from pydantic import Field
from ...common import CommonImageTo3DParamsConfig

class CommonPixal3DImageTo3DParamsConfig(CommonImageTo3DParamsConfig):
    ss_sampling_steps: Union[int, str] = Field(default=12, description="Sparse-structure diffusion sampling steps.")
    ss_guidance_strength: Union[float, str] = Field(default=7.5, description="Sparse-structure classifier-free guidance strength.")
    ss_guidance_rescale: Union[float, str] = Field(default=0.7, description="Sparse-structure guidance rescale factor.")
    ss_rescale_t: Union[float, str] = Field(default=5.0, description="Sparse-structure timestep rescale factor.")
    shape_slat_sampling_steps: Union[int, str] = Field(default=12, description="Shape structured-latent sampling steps.")
    shape_slat_guidance_strength: Union[float, str] = Field(default=7.5, description="Shape structured-latent classifier-free guidance strength.")
    shape_slat_guidance_rescale: Union[float, str] = Field(default=0.5, description="Shape structured-latent guidance rescale factor.")
    shape_slat_rescale_t: Union[float, str] = Field(default=3.0, description="Shape structured-latent timestep rescale factor.")
    tex_slat_sampling_steps: Union[int, str] = Field(default=12, description="Texture structured-latent sampling steps.")
    tex_slat_guidance_strength: Union[float, str] = Field(default=1.0, description="Texture structured-latent classifier-free guidance strength.")
    tex_slat_guidance_rescale: Union[float, str] = Field(default=0.0, description="Texture structured-latent guidance rescale factor.")
    tex_slat_rescale_t: Union[float, str] = Field(default=3.0, description="Texture structured-latent timestep rescale factor.")
    max_num_tokens: Union[int, str] = Field(default=49152, description="Maximum number of structured-latent tokens processed per stage.")
    texture_size: Union[int, str] = Field(default=4096, description="Baked texture size (pixels) applied when exporting the GLB.")
    decimation_target: Union[int, str] = Field(default=1000000, description="Target face count applied during mesh decimation before GLB export.")
