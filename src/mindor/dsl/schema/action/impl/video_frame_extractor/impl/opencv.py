from pydantic import model_validator
from .common import CommonVideoFrameExtractorActionConfig

class OpencvVideoFrameExtractorActionConfig(CommonVideoFrameExtractorActionConfig):
    @model_validator(mode="after")
    def validate_fps_unsupported(self):
        # `fps` (uniform-grid resampling) needs a filter graph that opencv
        # doesn't provide; use the ffmpeg driver for that mode.
        if self.fps is not None:
            raise ValueError("'fps' is not supported by the opencv driver; use the ffmpeg driver")
        return self
