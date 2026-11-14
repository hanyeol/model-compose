from typing import Union, Optional, List, Any
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class VideoFrameAnalyzerMetric(str, Enum):
    """Base enum shared by every video-frame-analyzer driver's metric set.

    Intentionally empty: Python enums with members can't be subclassed, so
    each driver (native, opencv, ...) extends this blank base to declare
    its own metrics while keeping a common parent type for schema wiring.
    """
    pass

class CommonVideoFrameAnalyzerActionConfig(CommonActionConfig):
    metric: VideoFrameAnalyzerMetric = Field(..., description="Kind of measurement performed on the frame sequence.")
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze; a flat list, list of batches, or stream of batches.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Source frame rate in frames per second; required for metrics that interpret cadence (e.g. pulldown period in duplicate_frames).")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether partial measurements are emitted incrementally as frames arrive; some metrics require the full sequence and ignore this flag.")
