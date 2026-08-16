from typing import Union
from pydantic import Field
from .common import CommonImageCompressorActionConfig

class OxipngImageCompressorActionConfig(CommonImageCompressorActionConfig):
    level: Union[int, str] = Field(default=4, description="Oxipng optimization level from 0 to 6; higher values produce smaller and slower output.")
