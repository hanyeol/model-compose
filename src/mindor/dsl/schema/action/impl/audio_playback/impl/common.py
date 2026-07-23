from typing import Union, Optional, List
from enum import Enum
from pydantic import Field, model_validator
from ...common import CommonActionConfig

class AudioPlaybackSink(str, Enum):
    SYSTEM = "system"
    DEVICE = "device"

class CommonAudioPlaybackActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio(s) — file path, URL, bytes, stream resource, or variable reference.")
    sink: Union[AudioPlaybackSink, str] = Field(default=AudioPlaybackSink.SYSTEM, description="Output target: 'system' for the OS default output device, 'device' for a specific device.")
    device: Optional[Union[int, str]] = Field(default=None, description="Device index or name; required when sink='device'.")
    volume: Union[float, str] = Field(default=1.0, description="Linear playback gain (1.0 = unchanged, 0.0 = mute).")
    duration: Optional[Union[str, float]] = Field(default=None, description="Maximum playback duration; None plays to end of input.")
    blocking: Union[bool, str] = Field(default=True, description="Wait for playback to finish before returning.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of inputs per batch when 'audio' is a list or stream.")

    @model_validator(mode="after")
    def validate_sink(self):
        # Only enforce the device-required rule for the enum literal. When
        # sink is a variable expression like "${input.sink}", pydantic keeps
        # it as a raw string and the runtime resolver validates the resolved
        # value against the device param.
        if self.sink == AudioPlaybackSink.DEVICE and self.device is None:
            raise ValueError("'device' must be provided when sink='device'.")
        return self
