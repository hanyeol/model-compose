from typing import Union, Optional, Dict
from pydantic import Field
from .common import CommonMediaDownloaderActionConfig

class YtdlpMediaDownloaderActionConfig(CommonMediaDownloaderActionConfig):
    format_selector: Optional[str] = Field(default=None, description="yt-dlp format selector expression (e.g., 'bestaudio/best', 'bestvideo[height<=720]+bestaudio').")
    extract_audio: Union[bool, str] = Field(default=False, description="Whether to extract the audio track only via yt-dlp's FFmpegExtractAudio postprocessor.")
    video_format: Optional[str] = Field(default=None, description="Target video container preferred when merging separate streams (e.g., mp4, webm).")
    audio_format: Optional[str] = Field(default=None, description="Target audio container when extracting audio (e.g., mp3, m4a, opus).")
    cookies: Dict[str, str] = Field(default_factory=dict, description="Cookies sent with the download request as name/value pairs.")
