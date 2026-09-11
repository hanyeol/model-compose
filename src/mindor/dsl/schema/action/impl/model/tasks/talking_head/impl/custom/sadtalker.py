from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ..common import CommonTalkingHeadParamsConfig, CommonTalkingHeadModelActionConfig

class SadTalkerEnhancer(str, Enum):
    GFPGAN         = "gfpgan"
    RESTORE_FORMER = "RestoreFormer"

class SadTalkerBackgroundEnhancer(str, Enum):
    REALESRGAN = "realesrgan"

class SadTalkerTalkingHeadParamsConfig(CommonTalkingHeadParamsConfig):
    ref_eyeblink: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Reference video whose eye-blink motion is transferred onto the output.")
    ref_pose: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Reference video whose head-pose motion is transferred onto the output.")
    pose_style: Union[int, str] = Field(default=0, description="Head-pose style index in [0, 46].")
    expression_scale: Union[float, str] = Field(default=1.0, description="Multiplier applied to facial expression intensity.")
    input_yaw: Optional[Union[List[int], str]] = Field(default=None, description="Manual yaw keyframes (degrees) that override predicted head rotation.")
    input_pitch: Optional[Union[List[int], str]] = Field(default=None, description="Manual pitch keyframes (degrees) that override predicted head rotation.")
    input_roll: Optional[Union[List[int], str]] = Field(default=None, description="Manual roll keyframes (degrees) that override predicted head rotation.")
    still: Union[bool, str] = Field(default=False, description="Keep the head still (only mouth moves); recommended with `full` preprocess.")
    enhancer: Optional[Union[SadTalkerEnhancer, str]] = Field(default=None, description="Face enhancer applied to the rendered frames.")
    background_enhancer: Optional[Union[SadTalkerBackgroundEnhancer, str]] = Field(default=None, description="Background super-resolution enhancer applied to the rendered frames.")
    face3dvis: Union[bool, str] = Field(default=False, description="Render an additional 3D face visualization video alongside the output.")
    size: Union[int, str] = Field(default=256, description="Face renderer resolution; matches the loaded preset (256 or 512).")
    facerender_batch_size: Union[int, str] = Field(default=2, description="Batch size used by the face renderer inference loop.")

class SadTalkerTalkingHeadModelActionConfig(CommonTalkingHeadModelActionConfig):
    params: SadTalkerTalkingHeadParamsConfig = Field(default_factory=SadTalkerTalkingHeadParamsConfig, description="SadTalker generation parameters.")
