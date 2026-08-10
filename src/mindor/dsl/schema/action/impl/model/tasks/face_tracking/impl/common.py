from typing import Union, List, Any
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceTrackingParamsConfig(BaseModel):
    similarity_threshold: Union[float, str] = Field(default=0.4, description="Cosine similarity threshold for grouping faces into the same person cluster.")
    min_face_size: Union[int, str] = Field(default=0, description="Minimum face bounding box size in pixels. 0 disables the filter.")
    min_frame_count: Union[int, str] = Field(default=1, description="Discard tracks that appear in fewer than this many frames.")
    max_face_count_per_frame: Union[int, str] = Field(default=0, description="Maximum number of faces to keep per frame. 0 disables the limit.")
    merge_gap: Union[float, str] = Field(default=0.0, description="Merge adjacent segments separated by less than this many seconds.")

class CommonFaceTrackingModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze. May be a single frame, a flat list, a list of batches, or a stream of batches.")
    frame_rate: Union[float, str] = Field(..., description="Frames per second used to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch. Broadcast when scalar; paired per batch when list/stream.")
    return_embedding: Union[bool, str] = Field(default=False, description="Whether to include the track's L2-normalized identity centroid embedding.")
    return_image: Union[bool, str] = Field(default=False, description="Whether to include a representative aligned face image per segment.")
    bounding_box_padding: Union[float, str] = Field(default=0.0, description="Padding ratio to expand each face crop's bounding box.")
    batch_size: Union[int, str] = Field(default=1, description="Frame batches per iteration.")
    params: CommonFaceTrackingParamsConfig = Field(default_factory=CommonFaceTrackingParamsConfig, description="Face tracking parameters.")
