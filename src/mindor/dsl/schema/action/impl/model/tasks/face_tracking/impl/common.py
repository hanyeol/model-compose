from typing import Union, List, Any
from pydantic import BaseModel, Field, model_validator
from ...common import CommonModelActionConfig

class CommonFaceTrackingParamsConfig(BaseModel):
    similarity_threshold: Union[float, str] = Field(default=0.4, description="Cosine similarity threshold that groups faces into the same person cluster.")
    min_face_size: Union[int, str] = Field(default=0, description="Minimum face bounding box size in pixels; 0 disables the filter.")
    min_frame_count: Union[int, str] = Field(default=1, description="Tracks appearing in fewer than this many frames are discarded.")
    max_face_count_per_frame: Union[int, str] = Field(default=0, description="Maximum number of faces kept per frame; 0 means unbounded.")
    merge_gap: Union[float, str] = Field(default=0.5, description="Extra seconds a person may be undetected before their segment is split; consecutive frames always merge.")
    max_track_distance: Union[float, str] = Field(default=1.5, description="Maximum distance a track may move between consecutive detections, as a multiple of the face size; 0 disables the check.")

class CommonFaceTrackingModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze; a single frame, flat list, list of batches, or stream of batches.")
    frame_rate: Union[float, str] = Field(..., description="Frame rate in frames per second used to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch; scalar values broadcast, lists pair per batch.")
    return_tracks: Union[bool, str] = Field(default=True, description="Whether the per-person track list is included in the result.")
    return_embedding: Union[bool, str] = Field(default=False, description="Whether each track's L2-normalized identity centroid embedding is included in the result.")
    return_track_image: Union[bool, str] = Field(default=False, description="Whether the source frame cropped to the face bounding box is included on each face; also emitted per-frame when 'return_frames' is enabled.")
    return_frames: Union[bool, str] = Field(default=False, description="Whether a frame-centric view is included alongside tracks, tagging each face by its track ID.")
    return_frame_image: Union[bool, str] = Field(default=False, description="Whether the source frame image is included in each per-frame view; requires 'return_frames' to be enabled.")
    return_metadata: Union[bool, str] = Field(default=False, description="Whether processing metadata (frame_count, ...) is included; a 'metadata' chunk is appended in streaming mode.")
    bounding_box_padding: Union[float, str] = Field(default=0.0, description="Ratio by which each face bounding box is expanded before cropping.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether per-frame views and confirmed segments are emitted incrementally as an event stream.")
    params: CommonFaceTrackingParamsConfig = Field(default_factory=CommonFaceTrackingParamsConfig, description="Clustering and filtering parameters applied to detected faces.")

    @model_validator(mode="after")
    def validate_return_tracks_or_frames(self):
        if self.return_tracks is False and self.return_frames is False:
            raise ValueError("Either 'return_tracks' or 'return_frames' must be true.")
        if self.return_frame_image is True and self.return_frames is False:
            raise ValueError("'return_frame_image' requires 'return_frames' to be true.")
        return self
