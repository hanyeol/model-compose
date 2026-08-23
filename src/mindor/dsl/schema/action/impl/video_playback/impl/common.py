from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonVideoPlaybackActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Input video to play — a file path, URL, bytes, stream, or variable reference.")
    window_title: Optional[Union[str, None]] = Field(default=None, description="Title of the playback window.")
    window_size: Optional[Union[str, None]] = Field(default=None, description="Window size as 'WIDTHxHEIGHT' (e.g. '1280x720'); when unset, uses the video's native size.")
    fullscreen: Union[bool, str] = Field(default=False, description="Whether to open the playback window in fullscreen mode.")
    always_on_top: Union[bool, str] = Field(default=False, description="Whether the playback window stays above other windows.")
    borderless: Union[bool, str] = Field(default=False, description="Whether the playback window is drawn without OS window borders.")
    mute: Union[bool, str] = Field(default=False, description="Whether to disable audio playback for input tracks.")
    volume: Union[int, str] = Field(default=100, description="Audio playback volume from 0 (mute) to 100 (unchanged).")
    duration: Optional[Union[str, float]] = Field(default=None, description="Maximum playback duration; when unset, playback runs to the end of the input.")
    wait_for_finish: Union[bool, str] = Field(default=True, description="Whether the action waits for playback to finish before returning.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of inputs processed per batch when `video` is a list or stream.")
