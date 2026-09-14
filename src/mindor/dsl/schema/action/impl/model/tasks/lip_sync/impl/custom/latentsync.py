from typing import Union
from pydantic import Field
from ..common import CommonLipSyncParamsConfig, CommonLipSyncModelActionConfig

class LatentSyncLipSyncParamsConfig(CommonLipSyncParamsConfig):
    inference_steps: Union[int, str] = Field(default=20, description="Number of diffusion denoising steps.")
    guidance_scale: Union[float, str] = Field(default=1.5, description="Classifier-free guidance scale applied during sampling.")
    enable_deepcache: Union[bool, str] = Field(default=False, description="Whether to enable DeepCache for a ~2x speedup at a small quality cost.")
    use_float16: Union[bool, str] = Field(default=True, description="Whether to run the pipeline in float16 for a memory and latency win.")

class LatentSyncLipSyncModelActionConfig(CommonLipSyncModelActionConfig):
    params: LatentSyncLipSyncParamsConfig = Field(default_factory=LatentSyncLipSyncParamsConfig, description="LatentSync generation parameters.")
