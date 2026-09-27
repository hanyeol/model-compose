from typing import Union, Optional, Literal, Dict, List, Any, Annotated
from pydantic import BaseModel, Field
from .common import CommonMediaDownloaderActionConfig

class YtdlpVideoFormatSpec(BaseModel):
    media: Literal[ "video" ] = Field(..., description="Kind of media stream to download.")
    container: Optional[str] = Field(default=None, description="Target video container (e.g., mp4, webm, mkv).")
    codec: Optional[str] = Field(default=None, description="Preferred video codec prefix (e.g., avc1, vp9).")
    max_height: Optional[Union[int, str]] = Field(default=None, description="Maximum video height in pixels.")
    max_fps: Optional[Union[int, str]] = Field(default=None, description="Maximum frame rate.")
    max_bitrate: Optional[Union[int, str]] = Field(default=None, description="Maximum video bitrate in kbps.")
    max_filesize: Optional[Union[int, str]] = Field(default=None, description="Maximum filesize as a yt-dlp size expression (e.g., 50M, 1G).")
    hdr: Optional[Union[bool, str]] = Field(default=None, description="Whether to prefer HDR streams.")
    prefer_free_formats: Optional[Union[bool, str]] = Field(default=None, description="Whether to prefer patent-free formats such as webm, opus, and vp9.")

class YtdlpAudioFormatSpec(BaseModel):
    media: Literal[ "audio" ] = Field(..., description="Kind of media stream to download.")
    codec: Optional[str] = Field(default=None, description="Target audio codec (e.g., mp3, m4a, opus, vorbis, flac, wav).")
    max_bitrate: Optional[Union[int, str]] = Field(default=None, description="Maximum audio bitrate in kbps.")
    max_filesize: Optional[Union[int, str]] = Field(default=None, description="Maximum filesize as a yt-dlp size expression (e.g., 50M, 1G).")
    prefer_free_formats: Optional[Union[bool, str]] = Field(default=None, description="Whether to prefer patent-free formats such as opus and vorbis.")

YtdlpFormatSpec = Annotated[
    Union[
        YtdlpVideoFormatSpec,
        YtdlpAudioFormatSpec
    ],
    Field(discriminator="media"),
]

class YtdlpMediaDownloaderActionConfig(CommonMediaDownloaderActionConfig):
    format: Optional[Union[YtdlpFormatSpec, str]] = Field(default=None, description="Download format as a preset name (e.g., mp3, mp4), a raw yt-dlp format expression, or a structured spec.")
    cookies: Union[List[Dict[str, Any]], str] = Field(default_factory=list, description="Cookies sent with the download request, in the shape returned by web-browser's get-cookies.")
    extractor_args: Union[Dict[str, Dict[str, Any]], str] = Field(default_factory=dict, description="Extractor-specific arguments keyed by extractor name, mirroring yt-dlp's --extractor-args.")
    js_runtimes: Union[List[str], str] = Field(default="deno", description="JavaScript runtimes yt-dlp may use to solve player challenges, in priority order; each entry may carry a path as RUNTIME:PATH.")
