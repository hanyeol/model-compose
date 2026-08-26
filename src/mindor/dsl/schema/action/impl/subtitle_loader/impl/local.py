from typing import Union, Optional, List
from pydantic import Field
from .common import CommonSubtitleLoaderActionConfig

class LocalSubtitleLoaderActionConfig(CommonSubtitleLoaderActionConfig):
    source: Union[List[str], str] = Field(..., description="Subtitle file source, or list of sources, as path, upload stream, or raw text.")
    format: Optional[str] = Field(default=None, description="Subtitle format (e.g. 'srt', 'vtt', 'ass'); inferred from file extension or content when omitted.")
    encoding: Optional[str] = Field(default=None, description="Text encoding (e.g. 'utf-8-sig'); auto-detected when omitted.")
