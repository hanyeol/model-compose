from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonShotBoundaryDetectionParamsConfig(BaseModel):
    threshold: Union[float, str] = Field(default=0.5, description="Confidence threshold above which a frame is treated as a shot boundary (0.0 - 1.0).")

class CommonShotBoundaryDetectionModelActionConfig(CommonModelActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to analyze for shot boundaries.")
    start_time: Optional[str] = Field(default=None, description="Time in the source at which detection begins (e.g., 00:01:00, 60s).")
    end_time: Optional[str] = Field(default=None, description="Time in the source at which detection stops (e.g., 00:05:00, 300s).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether shot results are emitted incrementally as they are detected.")
    params: CommonShotBoundaryDetectionParamsConfig = Field(default_factory=CommonShotBoundaryDetectionParamsConfig, description="Detection thresholds applied to the shot boundary detector.")
