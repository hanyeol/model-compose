from typing import Union, Optional, List
from pydantic import Field
from ..common import CommonTalkingHeadParamsConfig, CommonTalkingHeadModelActionConfig

class EchoMimicTalkingHeadParamsConfig(CommonTalkingHeadParamsConfig):
    pose: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Optional reference video/pose sequence driving head or half-body motion (v2 uses this for half-body).")
    width: Union[int, str] = Field(default=512, description="Output frame width in pixels.")
    height: Union[int, str] = Field(default=512, description="Output frame height in pixels.")
    inference_steps: Union[int, str] = Field(default=30, description="Number of diffusion inference steps.")
    cfg_scale: Union[float, str] = Field(default=2.5, description="Classifier-free guidance scale.")
    context_frames: Union[int, str] = Field(default=12, description="Number of frames processed per temporal context window.")
    context_overlap: Union[int, str] = Field(default=3, description="Frame overlap between consecutive temporal windows.")
    motion_sync: Union[bool, str] = Field(default=False, description="Enable motion-sync mode which extracts motion cues from the reference `pose` video.")
    sample_rate: Union[int, str] = Field(default=16000, description="Audio sample rate the model expects; resampling is applied if the input differs.")

class EchoMimicTalkingHeadModelActionConfig(CommonTalkingHeadModelActionConfig):
    params: EchoMimicTalkingHeadParamsConfig = Field(default_factory=EchoMimicTalkingHeadParamsConfig, description="EchoMimic generation parameters.")
