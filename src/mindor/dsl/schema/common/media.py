from typing import Union
from pydantic import BaseModel, Field

class MediaClipSpanConfig(BaseModel):
    start_time: Union[str, float, int] = Field(..., description="Clip start time (e.g. '00:00:10', '10s', 10.5).")
    end_time: Union[str, float, int] = Field(..., description="Clip end time (e.g. '00:00:20', '20s', 20.0).")
