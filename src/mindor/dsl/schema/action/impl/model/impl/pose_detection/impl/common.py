from typing import Union, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonPoseDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s) for pose detection.")
    num_poses: Union[int, str] = Field(default=1, description="Maximum number of poses to detect per image (>= 1).")
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum pose-detection confidence threshold (0.0 - 1.0).")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum keypoint-presence confidence (0.0 - 1.0).")
    min_tracking_confidence: Union[float, str] = Field(default=0.5, description="Minimum tracking confidence (0.0 - 1.0). Reserved for future video running mode.")
    include_keypoints: Union[bool, str] = Field(default=True, description="Include 2D pose keypoints (pixel coordinates) in the result.")
    include_keypoints_3d: Union[bool, str] = Field(default=False, description="Include real-world 3D keypoints in meters (hip-centered).")
    include_segmentation_mask: Union[bool, str] = Field(default=False, description="Include per-pose segmentation mask (PNG-encoded).")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")
