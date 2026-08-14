from typing import Literal, Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonPoseDetectionParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum confidence a returned detection must reach.")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum presence confidence a keypoint must reach.")
    min_tracking_confidence: Union[float, str] = Field(default=0.5, description="Minimum tracking confidence in video mode.")

class CommonPoseDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to detect poses in.")
    max_pose_count: Union[int, str] = Field(default=1, description="Maximum number of poses returned per image.")
    skeleton_format: Union[Literal[ "natural", "openpose" ], str] = Field(default="natural", description="Layout used when rendering the skeleton image.")
    return_keypoints: Union[bool, str] = Field(default=True, description="Whether natural-layout 2D keypoints are included in the result.")
    return_keypoints_3d: Union[bool, str] = Field(default=False, description="Whether 3D world keypoints (meters, hip-centered) are included in the result.")
    return_openpose_keypoints: Union[bool, str] = Field(default=False, description="Whether OpenPose BODY_18 keypoints are included in the result.")
    return_segmentation_mask: Union[bool, str] = Field(default=False, description="Whether the per-pose segmentation mask is included in the result.")
    return_skeleton_image: Union[bool, str] = Field(default=False, description="Whether a rendered per-pose skeleton image is included in the result.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonPoseDetectionParamsConfig = Field(default_factory=CommonPoseDetectionParamsConfig, description="Detection confidence thresholds applied to the pose detector.")
