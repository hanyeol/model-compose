from typing import Literal, Union, List, Any
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonPoseTrackingParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum detection confidence.")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum keypoint presence confidence.")
    min_pose_size: Union[int, str] = Field(default=0, description="Minimum pose bounding box size in pixels. 0 disables the filter.")
    min_frame_count: Union[int, str] = Field(default=1, description="Discard tracks that appear in fewer than this many frames.")
    max_pose_count_per_frame: Union[int, str] = Field(default=0, description="Maximum number of poses to keep per frame. 0 disables the limit.")
    merge_gap: Union[float, str] = Field(default=0.0, description="Extra seconds a person may go undetected before their segment is split. Consecutive frames always merge.")

class CommonPoseTrackingModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze. May be a single frame, a flat list, a list of batches, or a stream of batches.")
    frame_rate: Union[float, str] = Field(..., description="Frames per second used to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch. Broadcast when scalar; paired per batch when list/stream.")
    skeleton_format: Union[Literal[ "natural", "openpose" ], str] = Field(default="natural", description="Skeleton image layout.")
    return_keypoints: Union[bool, str] = Field(default=True, description="Return the representative frame's natural-layout 2D keypoints per segment.")
    return_openpose_keypoints: Union[bool, str] = Field(default=False, description="Return the representative frame's OpenPose BODY_18 keypoints per segment.")
    return_skeleton_image: Union[bool, str] = Field(default=False, description="Return a skeleton image for each segment's representative frame.")
    return_image: Union[bool, str] = Field(default=False, description="Return the cropped source frame around each segment's representative pose.")
    bounding_box_padding: Union[float, str] = Field(default=0.0, description="Padding ratio to expand each pose crop's bounding box.")
    batch_size: Union[int, str] = Field(default=1, description="Frame batches per iteration.")
    params: CommonPoseTrackingParamsConfig = Field(default_factory=CommonPoseTrackingParamsConfig, description="Pose tracking parameters.")
