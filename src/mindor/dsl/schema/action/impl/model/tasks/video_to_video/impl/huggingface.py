from typing import Union, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .common import CommonVideoToVideoParamsConfig, CommonVideoToVideoModelActionConfig

class AnimateDiffFreeNoiseConfig(BaseModel):
    context_length: Union[int, str] = Field(default=16, description="FreeNoise sliding-window length in frames.")
    context_stride: Union[int, str] = Field(default=4, description="Frame stride between successive FreeNoise windows.")
    weighting_scheme: str = Field(default="pyramid", description="Window weighting scheme (e.g. 'pyramid', 'flat').")

class AnimateDiffHuggingfaceVideoToVideoParamsConfig(CommonVideoToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=25, description="Number of diffusion inference steps.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale applied during sampling.")
    denoise_strength: Union[float, str] = Field(default=0.5, description="Denoising strength; higher values follow the prompt more, lower values preserve the input video.")
    ip_adapter_scale: Union[float, Dict[str, Any], List[Union[float, Dict[str, Any]]], str] = Field(default=0.6, description="IP-Adapter influence when a reference image is provided; scalar broadcasts to every adapter, list gives per-adapter weights, dict with 'down'/'mid'/'up' keys gives per-block weights (InstantStyle).")
    controlnet_conditioning_scale: Union[float, List[float], str] = Field(default=1.0, description="Strength of each ControlNet's influence; scalar or per-ControlNet list.")
    control_guidance_start: Union[float, List[float], str] = Field(default=0.0, description="Fraction of total steps after which each ControlNet starts applying.")
    control_guidance_end: Union[float, List[float], str] = Field(default=1.0, description="Fraction of total steps after which each ControlNet stops applying.")
    clip_skip: Optional[Union[int, str]] = Field(default=None, description="Number of final CLIP text-encoder layers to skip; '2' matches common anime SD1.5 recipes.")
    free_noise: Optional[AnimateDiffFreeNoiseConfig] = Field(default=None, description="Enable FreeNoise sliding-window sampling for clips longer than the motion adapter's native window.")
    decode_chunk_size: Optional[Union[int, str]] = Field(default=None, description="VAE latent decode chunk size; smaller values reduce VRAM at the cost of speed.")

class AnimateDiffHuggingfaceVideoToVideoModelActionConfig(CommonVideoToVideoModelActionConfig):
    reference_image: Optional[Union[Any, List[Any], List[List[Any]], str]] = Field(default=None, description="Per-IP-Adapter reference image(s); a single reference (one IP-Adapter), a list of references (one per IP-Adapter), or a per-input list of such lists for batched inputs.")
    attention_mask: Optional[Union[Any, List[Any], List[List[Any]], str]] = Field(default=None, description="Per-IP-Adapter spatial attention mask(s); a single mask (one IP-Adapter), a list of masks (one per IP-Adapter), or a per-input list of such lists for batched inputs. Use `null` within a per-adapter list to leave an adapter unmasked.")
    conditioning_frames: Optional[Union[Any, List[Any], List[List[Any]], str]] = Field(default=None, description="Per-ControlNet frame sequence(s) used as conditioning; a single reference (one ControlNet), a list of references (one per ControlNet), or a per-input list of such lists for batched inputs.")
    params: AnimateDiffHuggingfaceVideoToVideoParamsConfig = Field(default_factory=AnimateDiffHuggingfaceVideoToVideoParamsConfig, description="AnimateDiff video-to-video generation parameters.")

HuggingfaceVideoToVideoModelActionConfig = Union[
    AnimateDiffHuggingfaceVideoToVideoModelActionConfig,
]
