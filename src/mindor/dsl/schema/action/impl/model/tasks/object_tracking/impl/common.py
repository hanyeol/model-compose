from typing import Optional, Union, List, Any
from pydantic import BaseModel, Field, model_validator
from ...common import CommonModelActionConfig

class CommonObjectTrackingParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.25, description="Minimum confidence a returned detection must reach.")
    iou_threshold: Union[float, str] = Field(default=0.7, description="IoU threshold used by non-maximum suppression.")
    agnostic_nms: Union[bool, str] = Field(default=False, description="Whether non-maximum suppression is applied across classes rather than per class.")
    min_object_size: Union[int, str] = Field(default=0, description="Minimum object bounding box size in pixels; 0 disables the filter.")
    min_frame_count: Union[int, str] = Field(default=1, description="Tracks appearing in fewer than this many frames are discarded.")
    max_object_count_per_frame: Union[int, str] = Field(default=0, description="Maximum number of objects kept per frame; 0 means unbounded.")
    merge_gap: Union[float, str] = Field(default=0.5, description="Extra seconds an object may be undetected before its segment is split; consecutive frames always merge.")

class CommonObjectTrackingModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze; a single frame, flat list, list of batches, or stream of batches.")
    frame_rate: Union[float, str] = Field(..., description="Frame rate in frames per second used to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch; scalar values broadcast, lists pair per batch.")
    labels: Optional[Union[List[str], str]] = Field(default=None, description="Class labels detections are restricted to; unset returns all classes.")
    return_tracks: Union[bool, str] = Field(default=True, description="Whether the per-object track list is included in the result.")
    return_track_image: Union[bool, str] = Field(default=False, description="Whether the source frame cropped to the object bounding box is included on each object; also emitted per-frame when 'return_frames' is enabled.")
    return_frames: Union[bool, str] = Field(default=False, description="Whether a frame-centric view is included alongside tracks, tagging each object by its track ID.")
    return_frame_image: Union[bool, str] = Field(default=False, description="Whether the source frame image is included in each per-frame view; requires 'return_frames' to be enabled.")
    return_metadata: Union[bool, str] = Field(default=False, description="Whether processing metadata (frame_count, ...) is included; a 'metadata' chunk is appended in streaming mode.")
    bounding_box_padding: Union[float, str] = Field(default=0.0, description="Ratio by which each object bounding box is expanded before cropping.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether per-frame views and confirmed segments are emitted incrementally as an event stream.")
    params: CommonObjectTrackingParamsConfig = Field(default_factory=CommonObjectTrackingParamsConfig, description="Filtering and merging parameters applied to detected objects.")

    @model_validator(mode="after")
    def validate_return_tracks_or_frames(self):
        if self.return_tracks is False and self.return_frames is False:
            raise ValueError("Either 'return_tracks' or 'return_frames' must be true.")
        if self.return_frame_image is True and self.return_frames is False:
            raise ValueError("'return_frame_image' requires 'return_frames' to be true.")
        return self
