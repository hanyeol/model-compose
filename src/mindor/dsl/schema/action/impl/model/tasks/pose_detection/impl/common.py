from typing import Literal, Union, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonPoseDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s).")
    max_pose_count: Union[int, str] = Field(default=1, description="Maximum poses per image.")
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum detection confidence.")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum keypoint presence confidence.")
    min_tracking_confidence: Union[float, str] = Field(default=0.5, description="Minimum tracking confidence (reserved for video mode).")
    skeleton_format: Union[Literal[ "natural", "openpose" ], str] = Field(default="natural", description="Skeleton image layout.")
    return_keypoints: Union[bool, str] = Field(default=True, description="Return natural-layout 2D keypoints.")
    return_keypoints_3d: Union[bool, str] = Field(default=False, description="Return 3D world keypoints (meters, hip-centered).")
    return_openpose_keypoints: Union[bool, str] = Field(default=False, description="Return OpenPose BODY_18 keypoints.")
    return_segmentation_mask: Union[bool, str] = Field(default=False, description="Return per-pose segmentation mask.")
    return_skeleton_image: Union[bool, str] = Field(default=False, description="Return per-pose skeleton image.")
    batch_size: Union[int, str] = Field(default=1, description="Batch size.")
