from pydantic import model_validator
from .common import CommonVideoFrameExtractorActionConfig

class OpencvVideoFrameExtractorActionConfig(CommonVideoFrameExtractorActionConfig):
    @model_validator(mode="after")
    def validate_frame_rate_unsupported(self):
        # `frame_rate` (uniform-grid resampling) needs a filter graph that opencv
        # doesn't provide; use the ffmpeg driver for that mode.
        if self.frame_rate is not None:
            raise ValueError("'frame_rate' is not supported by the opencv driver; use the ffmpeg driver")
        return self
