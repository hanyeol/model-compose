from typing import Union, Optional
from pydantic import Field
from .common import CommonImageCompressorActionConfig

class PngquantImageCompressorActionConfig(CommonImageCompressorActionConfig):
    speed: Union[int, str] = Field(default=3, description="Pngquant speed from 1 (slowest/best) to 11 (fastest).")
    min_quality: Optional[Union[int, str]] = Field(default=None, description="Minimum acceptable quality from 0 to 100; save fails when output would fall below this.")
    max_quality: Optional[Union[int, str]] = Field(default=None, description="Maximum quality from 0 to 100 the encoder targets.")
