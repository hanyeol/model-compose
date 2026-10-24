from typing import Optional, Union, List, Any
from pydantic import BaseModel, Field, model_validator
from ...common import CommonModelActionConfig

class CommonActiveSpeakerDetectionParamsConfig(BaseModel):
    smoothing_window: Union[str, float, int] = Field(default="0.4s", description="Window size for temporal smoothing of per-frame speaking scores (e.g., 400ms).")
    threshold: Union[float, str] = Field(default=0.0, description="Score threshold above which a frame is considered speaking; the model emits logits, so 0.0 is the natural cutoff.")
    min_segment_duration: Union[str, float, int] = Field(default="0.3s", description="Minimum speaking-segment duration; shorter segments are discarded (e.g., 300ms).")
    merge_gap: Union[str, float, int] = Field(default="0.2s", description="Adjacent speaking segments on the same track separated by no more than this gap are merged (e.g., 200ms).")

class CommonActiveSpeakerDetectionModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images aligned with `tracks`; a single frame, flat list, list of batches, or stream of batches. Reuse the same frames passed to the paired face-tracking component.")
    timestamps: Optional[Union[float, List[float], List[List[float]], str]] = Field(default=None, description="Per-frame timestamps in seconds paired with `frames`; overrides `frame_rate`/`time_offset` when set.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Frames per second; required when `timestamps` is unset to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch; scalar values broadcast, lists pair per batch.")
    audio: Union[str, List[str]] = Field(..., description="Audio paired with `frames`; a single input or a list matching the per-batch structure.")
    tracks: Union[Any, List[Any], str] = Field(..., description="Face-tracking detections paired with `frames`; the per-frame `detections` list produced by a face-tracking component with `return_detections: true`.")
    return_speakers: Union[bool, str] = Field(default=True, description="Whether the per-track speaking segment list is included in the result.")
    return_frame_scores: Union[bool, str] = Field(default=False, description="Whether per-frame speaking scores are included on each track.")
    return_timeline: Union[bool, str] = Field(default=False, description="Whether an across-tracks active-speaker timeline is included.")
    return_metadata: Union[bool, str] = Field(default=False, description="Whether processing metadata (frame_count, track_count, ...) is included.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether speaking segments are emitted incrementally as they are confirmed.")
    params: CommonActiveSpeakerDetectionParamsConfig = Field(default_factory=CommonActiveSpeakerDetectionParamsConfig, description="Score-shaping parameters applied to the per-frame outputs.")

    @model_validator(mode="after")
    def validate_return_flags(self):
        if self.return_speakers is False and self.return_timeline is False:
            raise ValueError("Either 'return_speakers' or 'return_timeline' must be true.")
        if self.return_frame_scores is True and self.return_speakers is False:
            raise ValueError("'return_frame_scores' requires 'return_speakers' to be true.")
        return self

    @model_validator(mode="after")
    def validate_timestamps_or_frame_rate(self):
        if self.timestamps is None and self.frame_rate is None:
            raise ValueError("Either 'timestamps' or 'frame_rate' must be set.")
        return self
