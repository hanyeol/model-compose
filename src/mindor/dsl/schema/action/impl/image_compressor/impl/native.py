from typing import Union
from pydantic import Field
from .common import CommonImageCompressorActionConfig

class NativeImageCompressorActionConfig(CommonImageCompressorActionConfig):
    compress_level: Union[int, str] = Field(default=9, description="DEFLATE compression level from 0 to 9; higher values produce smaller and slower output.")
