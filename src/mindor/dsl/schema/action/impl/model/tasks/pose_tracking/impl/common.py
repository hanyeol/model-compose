from typing import Literal, Optional, Tuple, Union, List, Any
from pydantic import BaseModel, Field, model_validator
from ...common import CommonModelActionConfig

class CommonPoseTrackingParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum confidence a returned detection must reach.")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum presence confidence a keypoint must reach.")
    min_pose_size: Union[int, str] = Field(default=0, description="Minimum pose bounding box size in pixels; 0 disables the filter.")
    min_frame_count: Union[int, str] = Field(default=1, description="Tracks appearing in fewer than this many frames are discarded.")
    max_pose_count_per_frame: Union[int, str] = Field(default=0, description="Maximum number of poses kept per frame; 0 means unbounded.")
    merge_gap: Union[float, str] = Field(default=0.5, description="Extra seconds a person may be undetected before their segment is split; consecutive frames always merge.")

class CommonPoseTrackingModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze; a single frame, flat list, list of batches, or stream of batches.")
    frame_rate: Union[float, str] = Field(..., description="Frame rate in frames per second used to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch; scalar values broadcast, lists pair per batch.")
    skeleton_format: Union[Literal[ "natural", "openpose" ], str] = Field(default="natural", description="Layout used when rendering the skeleton image.")
    skeleton_background: Optional[Union[str, Tuple[int, int, int], Tuple[int, int, int, int], List[int]]] = Field(default=None, description="Skeleton canvas background: None yields a transparent RGBA PNG; a color (e.g. '#000000') flattens to that solid RGB fill.")
    return_tracks: Union[bool, str] = Field(default=True, description="Whether the per-person track list is included in the result.")
    return_keypoints: Union[bool, str] = Field(default=True, description="Whether natural-layout 2D keypoints are included on each pose; also emitted per-frame when 'return_frames' is enabled.")
    return_openpose_keypoints: Union[bool, str] = Field(default=False, description="Whether OpenPose BODY_18 keypoints are included on each pose; also emitted per-frame when 'return_frames' is enabled.")
    return_skeleton_image: Union[bool, str] = Field(default=False, description="Whether a rendered skeleton image is included on each pose; also emitted per-frame when 'return_frames' is enabled.")
    return_track_image: Union[bool, str] = Field(default=False, description="Whether the source frame cropped to the pose bounding box is included on each pose; also emitted per-frame when 'return_frames' is enabled.")
    return_frames: Union[bool, str] = Field(default=False, description="Whether a frame-centric view is included alongside tracks, tagging each pose by its track ID.")
    return_frame_image: Union[bool, str] = Field(default=False, description="Whether the source frame image is included in each per-frame view; requires 'return_frames' to be enabled.")
    return_metadata: Union[bool, str] = Field(default=False, description="Whether processing metadata (frame_count, ...) is included; a 'metadata' chunk is appended in streaming mode.")
    bounding_box_padding: Union[float, str] = Field(default=0.0, description="Ratio by which each pose bounding box is expanded before cropping.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether per-frame views and confirmed segments are emitted incrementally as an event stream.")
    params: CommonPoseTrackingParamsConfig = Field(default_factory=CommonPoseTrackingParamsConfig, description="Filtering and merging parameters applied to detected poses.")

    @model_validator(mode="after")
    def validate_return_tracks_or_frames(self):
        if self.return_tracks is False and self.return_frames is False:
            raise ValueError("Either 'return_tracks' or 'return_frames' must be true.")
        if self.return_frame_image is True and self.return_frames is False:
            raise ValueError("'return_frame_image' requires 'return_frames' to be true.")
        return self
