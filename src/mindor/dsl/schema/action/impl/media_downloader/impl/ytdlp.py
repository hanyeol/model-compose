from typing import Union, Optional, Literal, Dict, List, Any
from pydantic import BaseModel, Field
from .common import CommonMediaDownloaderActionConfig

class YtdlpFormatSpec(BaseModel):
    media: Literal[ "video", "audio" ] = Field(..., description="Kind of media stream to download.")
    container: Optional[str] = Field(default=None, description="Target container extension (e.g., mp3, m4a, mp4, webm).")
    codec: Optional[str] = Field(default=None, description="Preferred codec prefix (e.g., avc1, opus); routed to yt-dlp's vcodec/acodec filter based on `media`.")
    max_height: Optional[Union[int, str]] = Field(default=None, description="Maximum video height in pixels. Ignored when `media` is `audio`.")
    max_fps: Optional[Union[int, str]] = Field(default=None, description="Maximum frame rate. Ignored when `media` is `audio`.")
    max_bitrate: Optional[Union[int, str]] = Field(default=None, description="Maximum bitrate in kbps; applies to abr for `audio` media and vbr for `video` media.")
    max_filesize: Optional[Union[int, str]] = Field(default=None, description="Maximum filesize as a yt-dlp size expression (e.g., 50M, 1G).")
    hdr: Optional[Union[bool, str]] = Field(default=None, description="Whether to prefer HDR streams. Ignored when `media` is `audio`.")
    prefer_free_formats: Optional[Union[bool, str]] = Field(default=None, description="Whether to prefer patent-free formats such as webm, opus, and vp9.")

class YtdlpMediaDownloaderActionConfig(CommonMediaDownloaderActionConfig):
    format: Optional[Union[YtdlpFormatSpec, str]] = Field(default=None, description="Download format as a preset name (e.g., mp3, mp4), a raw yt-dlp format expression, or a structured spec.")
    cookies: Union[List[Dict[str, Any]], str] = Field(default_factory=list, description="Cookies sent with the download request, in the shape returned by web-browser's get-cookies.")
    extractor_args: Union[Dict[str, Dict[str, Any]], str] = Field(default_factory=dict, description="Extractor-specific arguments keyed by extractor name, mirroring yt-dlp's --extractor-args.")
    js_runtimes: Union[List[str], str] = Field(default="deno", description="JavaScript runtimes yt-dlp may use to solve player challenges, in priority order; each entry may carry a path as RUNTIME:PATH.")
