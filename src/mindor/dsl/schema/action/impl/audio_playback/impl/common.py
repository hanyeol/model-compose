from typing import Union, Optional, List
from enum import Enum
from pydantic import Field, model_validator
from ...common import CommonActionConfig

class AudioPlaybackSink(str, Enum):
    SYSTEM = "system"
    DEVICE = "device"

class CommonAudioPlaybackActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to play, or a list of audios.")
    sink: Union[AudioPlaybackSink, str] = Field(default=AudioPlaybackSink.SYSTEM, description="Playback output target: the OS default output or a specific device.")
    device: Optional[Union[int, str]] = Field(default=None, description="Output device index or name. Required when `sink` is `device`.")
    volume: Union[float, str] = Field(default=1.0, description="Linear playback gain, where 1.0 is unchanged and 0.0 is mute.")
    duration: Optional[Union[str, float]] = Field(default=None, description="Maximum playback duration; when unset, playback runs to the end of the input.")
    wait_for_finish: Union[bool, str] = Field(default=True, description="Whether the action waits for playback to finish before returning.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of inputs processed per batch when `audio` is a list or stream.")

    @model_validator(mode="after")
    def validate_sink(self):
        # Only enforce the device-required rule for the enum literal. When
        # sink is a variable expression like "${input.sink}", pydantic keeps
        # it as a raw string and the runtime resolver validates the resolved
        # value against the device param.
        if self.sink == AudioPlaybackSink.DEVICE and self.device is None:
            raise ValueError("'device' must be provided when sink='device'.")
        return self
