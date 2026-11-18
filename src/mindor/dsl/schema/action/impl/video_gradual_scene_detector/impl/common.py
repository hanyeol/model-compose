from typing import Union, Optional, List, Any
from pydantic import Field
from ...common import CommonActionConfig

class CommonVideoGradualSceneDetectorActionConfig(CommonActionConfig):
    frames: Union[Any, List[Any], str] = Field(..., description="Decoded frame sequence covering the full video; scanned for gradual transitions (fade / dissolve / wipe / slide).")
    frame_rate: Union[float, str] = Field(..., description="Source frame rate in frames per second; window lengths are derived from this.")
    known_boundaries: Optional[Union[List[Union[int, str]], str]] = Field(default=None, description="Frame indices of boundaries already known (typically from a hard-cut detector); windows around them are skipped so the same boundary is not re-reported.")
    batch_size: Union[int, str] = Field(default=1, description="Number of independent frame sequences processed per iteration.")
    streaming: Union[bool, str] = Field(default=False, description="Whether gradual-boundary results are emitted incrementally as windows are scanned.")
