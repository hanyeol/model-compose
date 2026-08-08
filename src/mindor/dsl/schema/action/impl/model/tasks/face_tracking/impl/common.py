from typing import Union, List, Any
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class FrameSegmentConfig(BaseModel):
    frames: Union[List[Any], str] = Field(..., description="Frame images belonging to this segment.")
    start_time: Union[str, float, int] = Field(..., description="Segment start time (e.g. '00:00:10', '10s', 10.5).")
    end_time: Union[str, float, int] = Field(..., description="Segment end time (e.g. '00:00:20', '20s', 20.0).")

class CommonFaceTrackingParamsConfig(BaseModel):
    similarity_threshold: Union[float, str] = Field(default=0.4, description="Cosine similarity threshold for grouping faces into the same person cluster.")
    min_face_size: Union[int, str] = Field(default=0, description="Minimum face bounding box size in pixels. 0 disables the filter.")
    min_appearances: Union[int, str] = Field(default=1, description="Discard clusters that appear in fewer than this many segments.")
    merge_gap: Union[float, str] = Field(default=0.0, description="Merge adjacent appearance intervals separated by less than this many seconds.")
    max_faces_per_frame: Union[int, str] = Field(default=0, description="Maximum number of faces to keep per frame. 0 disables the limit.")

class CommonFaceTrackingModelActionConfig(CommonModelActionConfig):
    segments: Union[List[FrameSegmentConfig], str] = Field(..., description="Frame segments to analyze. Each segment carries one or more frame images sharing a start_time/end_time range.")
    params: CommonFaceTrackingParamsConfig = Field(default_factory=CommonFaceTrackingParamsConfig, description="Face tracking parameters.")
