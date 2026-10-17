from typing import Union, Optional, List
from pydantic import Field
from .common import CommonMusicScoreLoaderActionConfig, MusicScoreLoaderFormat

class LocalMusicScoreLoaderActionConfig(CommonMusicScoreLoaderActionConfig):
    source: Union[List[str], str] = Field(..., description="Score file source, or list of sources, as path, upload stream, or raw bytes.")
    format: Optional[Union[MusicScoreLoaderFormat, str]] = Field(default=None, description="Score format (`midi` or `musicxml`); inferred from file extension or content when omitted.")
    part: Optional[Union[int, str]] = Field(default=None, description="Part index to extract; defaults to all parts in the score.")
