from typing import Union, Optional, List, Dict, Any
from pydantic import Field
from .common import CommonSubtitleLoaderActionConfig

class YtdlpSubtitleLoaderActionConfig(CommonSubtitleLoaderActionConfig):
    url: Union[List[str], str] = Field(..., description="Source URL, or list of URLs, whose subtitles are fetched.")
    languages: Optional[Union[List[str], str]] = Field(default=None, description="Preferred subtitle language, or list of languages in priority order, as BCP-47 or ISO 639-1 codes.")
    format: Optional[Union[str, List[str]]] = Field(default="srt", description="Subtitle file format to request from yt-dlp (e.g. 'srt', 'vtt', 'json3').")
    include_auto_generated: Union[bool, str] = Field(default=True, description="Whether to fall back to auto-generated captions when no human subtitle is available.")
    cookies: Union[List[Dict[str, Any]], str] = Field(default_factory=list, description="Cookies sent with the request, in the shape returned by web-browser's get-cookies.")
    extractor_args: Union[Dict[str, Dict[str, Any]], str] = Field(default_factory=dict, description="Extractor-specific arguments keyed by extractor name, mirroring yt-dlp's --extractor-args.")
    js_runtimes: Union[List[str], str] = Field(default="deno", description="JavaScript runtimes yt-dlp may use to solve player challenges, in priority order; each entry may carry a path as RUNTIME:PATH.")
