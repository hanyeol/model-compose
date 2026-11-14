from typing import Union, Optional, List, Any
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class VideoMotionEstimatorMode(str, Enum):
    """Base enum shared by every video-motion-estimator driver's mode set.

    Intentionally empty: Python enums with members can't be subclassed, so
    each driver (opencv, ...) extends this blank base to declare its own
    modes while keeping a common parent type for schema wiring.
    """
    pass

class CommonVideoMotionEstimatorActionConfig(CommonActionConfig):
    mode: VideoMotionEstimatorMode = Field(..., description="Kind of motion estimation performed on the frame sequence.")
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to estimate motion from; a flat list, list of batches, or stream of batches.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Source frame rate in frames per second; required to convert per-frame deltas into per-second rates (e.g. zoom_per_s, pan_px_per_s).")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether partial estimates are emitted incrementally as frames arrive; some modes require the full sequence and ignore this flag.")
