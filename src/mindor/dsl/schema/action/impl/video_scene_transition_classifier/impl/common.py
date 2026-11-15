from typing import Union, Optional, List, Any
from pydantic import Field
from ...common import CommonActionConfig

class CommonVideoSceneTransitionClassifierActionConfig(CommonActionConfig):
    scenes: Union[Any, List[Any], str] = Field(..., description="Scene list as produced by video-scene-detector; the boundary at each scene's end_frame is classified against the following scene.")
    frames: Union[Any, List[Any], str] = Field(..., description="Decoded frame sequence covering the full video; each boundary is classified by sampling a window of frames around it.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Source frame rate in frames per second; used to report fade/dissolve durations in seconds.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame batches processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether partial classifications are emitted incrementally as boundaries are processed.")
