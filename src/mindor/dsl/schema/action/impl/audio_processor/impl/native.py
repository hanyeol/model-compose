from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from .common import CommonAudioProcessorActionConfig, AudioProcessorActionMethod

class AudioProcessorHighpassActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.HIGHPASS]
    cutoff: Union[float, str] = Field(..., description="Cutoff frequency in Hz.")

class AudioProcessorLowpassActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.LOWPASS]
    cutoff: Union[float, str] = Field(..., description="Cutoff frequency in Hz.")

class AudioProcessorPitchShiftActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.PITCH_SHIFT]
    semitones: Union[float, str] = Field(..., description="Pitch shift amount in semitones (positive to raise, negative to lower).")

class AudioProcessorDcShiftActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.DC_SHIFT]
    offset: Optional[Union[float, str]] = Field(default=None, description="Additional DC offset applied after centering (-1.0 to 1.0). Defaults to 0.")

class AudioProcessorCompressorActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.COMPRESSOR]
    threshold: Union[float, str] = Field(default=-20.0, description="Threshold in dB above which compression applies.")
    ratio: Union[float, str] = Field(default=4.0, description="Compression ratio (e.g. 4.0 for 4:1).")
    attack: Union[str, float] = Field(default="1ms", description="Attack time (e.g. '1ms').")
    release: Union[str, float] = Field(default="100ms", description="Release time (e.g. '100ms').")

class AudioProcessorGainActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.GAIN]
    level: Union[float, str] = Field(..., description="Gain in dB (positive to boost, negative to attenuate).")

class AudioProcessorChorusActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.CHORUS]
    rate: Union[float, str] = Field(default=1.0, description="LFO rate in Hz.")
    depth: Union[float, str] = Field(default=0.25, description="Modulation depth (0.0 to 1.0).")
    feedback: Union[float, str] = Field(default=0.0, description="Feedback amount (0.0 to 1.0).")
    delay: Union[str, float] = Field(default="7ms", description="Centre delay time (e.g. '7ms').")
    mix: Union[float, str] = Field(default=0.5, description="Dry/wet mix (0.0 to 1.0).")

class AudioProcessorDelayActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.DELAY]
    time: Union[str, float] = Field(default="500ms", description="Delay time (e.g. '500ms').")
    feedback: Union[float, str] = Field(default=0.0, description="Feedback amount (0.0 to 1.0).")
    mix: Union[float, str] = Field(default=0.5, description="Dry/wet mix (0.0 to 1.0).")

class AudioProcessorReverbActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.REVERB]
    room_size: Union[float, str] = Field(default=0.5, description="Room size (0.0 to 1.0).")
    damping: Union[float, str] = Field(default=0.5, description="High-frequency damping (0.0 to 1.0).")
    wet_level: Union[float, str] = Field(default=0.33, description="Wet signal level (0.0 to 1.0).")
    dry_level: Union[float, str] = Field(default=0.4, description="Dry signal level (0.0 to 1.0).")
    width: Union[float, str] = Field(default=1.0, description="Stereo width (0.0 to 1.0).")

class AudioProcessorNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    level: Union[float, str] = Field(default=-20.0, description="Target RMS level in dBFS.")
    peak_limit: Union[float, str] = Field(default=0.85, description="Peak amplitude cap (0.0 to 1.0) applied after normalization.")

class AudioProcessorPeakLimitActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.PEAK_LIMIT]
    level: Union[float, str] = Field(default=0.95, description="Peak amplitude cap (0.0 to 1.0). Applied only if the input peak exceeds this value.")

class AudioProcessorTrimEdgesActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.TRIM_EDGES]
    threshold: Union[float, str] = Field(default=40.0, description="Silence threshold in dB below peak for edge trimming.")
    padding: Optional[Union[str, float]] = Field(default=None, description="Padding to restore at each edge when trimming shortens the audio (e.g. '100ms'). Defaults to 0.")

class AudioProcessorTrimSilenceActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.TRIM_SILENCE]
    window: Union[str, float] = Field(default="20ms", description="RMS analysis window size (e.g. '20ms').")
    threshold: Union[float, str] = Field(default=-40.0, description="Silence threshold in dBFS below which a window is considered silence.")
    min_silence: Union[str, float] = Field(default="200ms", description="Minimum trailing silence to keep (e.g. '200ms').")
    max_internal_silence: Union[str, float] = Field(default="1s", description="Cut audio after any internal silence gap longer than this (e.g. '1s').")
    fade: Union[str, float] = Field(default="30ms", description="Cosine fade-out duration at the trimmed end (e.g. '30ms').")

NativeAudioProcessorActionConfig = Annotated[
    Union[
        AudioProcessorHighpassActionConfig,
        AudioProcessorLowpassActionConfig,
        AudioProcessorPitchShiftActionConfig,
        AudioProcessorDcShiftActionConfig,
        AudioProcessorCompressorActionConfig,
        AudioProcessorGainActionConfig,
        AudioProcessorChorusActionConfig,
        AudioProcessorDelayActionConfig,
        AudioProcessorReverbActionConfig,
        AudioProcessorNormalizeActionConfig,
        AudioProcessorPeakLimitActionConfig,
        AudioProcessorTrimEdgesActionConfig,
        AudioProcessorTrimSilenceActionConfig,
    ],
    Field(discriminator="method")
]
