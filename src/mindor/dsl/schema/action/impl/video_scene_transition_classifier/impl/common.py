from typing import Union, Optional, List, Any
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class VideoSceneTransitionClassifierMode(str, Enum):
    """Base enum shared by every video-scene-transition-classifier driver's mode set.

    Intentionally empty: Python enums with members can't be subclassed, so
    each driver (native, ...) extends this blank base to declare its own
    modes while keeping a common parent type for schema wiring.
    """
    pass

class CommonVideoSceneTransitionClassifierActionConfig(CommonActionConfig):
    mode: VideoSceneTransitionClassifierMode = Field(..., description="Kind of transition classification performed on each scene boundary.")
    scenes: Union[Any, List[Any], str] = Field(..., description="Scene list as produced by video-scene-detector; the boundary at each scene's end_frame is classified against the following scene.")
    frames: Union[Any, List[Any], str] = Field(..., description="Decoded frame sequence covering the full video; each boundary is classified by sampling a window of frames around it.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Source frame rate in frames per second; used to report fade/dissolve durations in seconds.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether partial classifications are emitted incrementally as boundaries are processed.")
