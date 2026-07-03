from typing import Union, List
from pydantic import Field, model_validator
from ...common import CommonModelActionConfig

class CommonPoseDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s) for pose detection.")
    max_pose_count: Union[int, str] = Field(default=1, description="Maximum number of poses to detect per image (>= 1).")
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum pose-detection confidence threshold (0.0 - 1.0).")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum keypoint-presence confidence (0.0 - 1.0).")
    min_tracking_confidence: Union[float, str] = Field(default=0.5, description="Minimum tracking confidence (0.0 - 1.0). Reserved for future video running mode.")
    return_keypoints: Union[bool, str] = Field(default=True, description="Whether to return 2D pose keypoints (pixel coordinates) in the result.")
    return_keypoints_3d: Union[bool, str] = Field(default=False, description="Whether to return real-world 3D keypoints in meters (hip-centered).")
    return_segmentation_mask: Union[bool, str] = Field(default=False, description="Whether to return per-pose segmentation mask.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")

    @model_validator(mode="after")
    def validate_at_least_one_return(self):
        if self.return_keypoints is False and self.return_keypoints_3d is False and self.return_segmentation_mask is False:
            raise ValueError("At least one of 'return_keypoints', 'return_keypoints_3d', or 'return_segmentation_mask' must be true")
        return self
