from typing import Union, Literal, Optional, Annotated, Any
from pydantic import Field, Tag, Discriminator
from .common import CommonAudioProcessorActionConfig, AudioProcessorActionMethod, AudioProcessorNormalizeMode, AudioProcessorPeakLimitMode

def _peak_limit_mode_discriminator(v: Any) -> str:
    mode = v.get("mode") if isinstance(v, dict) else getattr(v, "mode", None)
    if mode is None:
        return AudioProcessorPeakLimitMode.HARD.value
    return mode.value if isinstance(mode, AudioProcessorPeakLimitMode) else mode

class AudioProcessorResampleActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.RESAMPLE]
    sample_rate: Union[int, str] = Field(..., description="Target sample rate in Hz (e.g. 44100, 48000).")

class AudioProcessorHighpassActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.HIGHPASS]
    cutoff: Union[float, str] = Field(..., description="Cutoff frequency in Hz.")

class AudioProcessorLowpassActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.LOWPASS]
    cutoff: Union[float, str] = Field(..., description="Cutoff frequency in Hz.")

class AudioProcessorBellActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.BELL]
    frequency: Union[float, str] = Field(..., description="Centre frequency of the bell in Hz.")
    gain: Union[float, str] = Field(..., description="Gain at the centre frequency in dB (positive to boost, negative to cut).")
    q: Union[float, str] = Field(default=0.707, description="Bell width (higher Q = narrower band). Defaults to 0.707.")

class AudioProcessorLowShelfActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.LOW_SHELF]
    frequency: Union[float, str] = Field(..., description="Shelf corner frequency in Hz (audio below this is affected).")
    gain: Union[float, str] = Field(..., description="Shelf gain in dB (positive to boost, negative to cut).")
    q: Union[float, str] = Field(default=0.707, description="Shelf slope (higher Q = steeper corner). Defaults to 0.707.")

class AudioProcessorHighShelfActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.HIGH_SHELF]
    frequency: Union[float, str] = Field(..., description="Shelf corner frequency in Hz (audio above this is affected).")
    gain: Union[float, str] = Field(..., description="Shelf gain in dB (positive to boost, negative to cut).")
    q: Union[float, str] = Field(default=0.707, description="Shelf slope (higher Q = steeper corner). Defaults to 0.707.")

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

class AudioProcessorNoiseGateActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NOISE_GATE]
    threshold: Union[float, str] = Field(default=-40.0, description="Threshold in dB below which the gate attenuates.")
    ratio: Union[float, str] = Field(default=10.0, description="Downward expansion ratio (higher = more aggressive gating).")
    attack: Union[str, float] = Field(default="1ms", description="Attack time (e.g. '1ms').")
    release: Union[str, float] = Field(default="100ms", description="Release time (e.g. '100ms').")

class AudioProcessorDistortionActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.DISTORTION]
    drive: Union[float, str] = Field(..., description="Drive amount in dB (higher = more aggressive distortion; typical range 15 to 40).")

class AudioProcessorSaturationActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.SATURATION]
    drive: Union[float, str] = Field(default=3.0, description="Drive amount in dB (subtle harmonic colour; typical range 1 to 8).")

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

class AudioProcessorRmsNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    mode: Literal[AudioProcessorNormalizeMode.RMS]
    level: Union[float, str] = Field(default=-20.0, description="Target RMS level in dBFS.")
    peak_limit: Union[float, str] = Field(default=0.85, description="Peak amplitude cap (0.0 to 1.0) applied after normalization.")

class AudioProcessorPeakNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    mode: Literal[AudioProcessorNormalizeMode.PEAK]
    level: Union[float, str] = Field(default=-1.0, description="Target peak level in dBFS (e.g. -1.0 for -1 dBFS headroom).")

class AudioProcessorLufsNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    mode: Literal[AudioProcessorNormalizeMode.LUFS]
    level: Union[float, str] = Field(default=-14.0, description="Target integrated loudness in LUFS (e.g. -14 for streaming, -9 to -12 for punchier masters).")
    tolerance: Union[float, str] = Field(default=0.5, description="Acceptable deviation from target in LU before verify loop re-iterates.")
    max_gain: Union[float, str] = Field(default=30.0, description="Maximum absolute gain in dB the verify loop may apply.")
    true_peak_ceiling: Union[float, str] = Field(default=-1.0, description="True-peak ceiling in dBTP enforced after loudness gain (e.g. -1.0 for -1 dBTP).")

AudioProcessorNormalizeActionConfig = Annotated[
    Union[
        AudioProcessorRmsNormalizeActionConfig,
        AudioProcessorPeakNormalizeActionConfig,
        AudioProcessorLufsNormalizeActionConfig,
    ],
    Field(discriminator="mode")
]

class AudioProcessorHardPeakLimitActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.PEAK_LIMIT]
    mode: Literal[AudioProcessorPeakLimitMode.HARD] = AudioProcessorPeakLimitMode.HARD
    level: Union[float, str] = Field(default=0.95, description="Peak amplitude cap (0.0 to 1.0). Applied only if the input peak exceeds this value.")

class AudioProcessorSmoothPeakLimitActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.PEAK_LIMIT]
    mode: Literal[AudioProcessorPeakLimitMode.SMOOTH]
    level: Union[float, str] = Field(default=-1.0, description="Ceiling in dBFS (e.g. -1.0 for -1 dBFS headroom).")
    release: Union[str, float] = Field(default="100ms", description="Release time (e.g. '100ms').")

AudioProcessorPeakLimitActionConfig = Annotated[
    Union[
        Annotated[AudioProcessorHardPeakLimitActionConfig, Tag(AudioProcessorPeakLimitMode.HARD.value)],
        Annotated[AudioProcessorSmoothPeakLimitActionConfig, Tag(AudioProcessorPeakLimitMode.SMOOTH.value)],
    ],
    Discriminator(_peak_limit_mode_discriminator)
]

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

class AudioProcessorFadeInActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.FADE_IN]
    duration: Union[str, float] = Field(default="20ms", description="Cosine fade-in duration at the start (e.g. '20ms').")

class AudioProcessorFadeOutActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.FADE_OUT]
    duration: Union[str, float] = Field(default="20ms", description="Cosine fade-out duration at the end (e.g. '20ms').")

NativeAudioProcessorActionConfig = Annotated[
    Union[
        AudioProcessorResampleActionConfig,
        AudioProcessorHighpassActionConfig,
        AudioProcessorLowpassActionConfig,
        AudioProcessorBellActionConfig,
        AudioProcessorLowShelfActionConfig,
        AudioProcessorHighShelfActionConfig,
        AudioProcessorPitchShiftActionConfig,
        AudioProcessorDcShiftActionConfig,
        AudioProcessorCompressorActionConfig,
        AudioProcessorNoiseGateActionConfig,
        AudioProcessorDistortionActionConfig,
        AudioProcessorSaturationActionConfig,
        AudioProcessorGainActionConfig,
        AudioProcessorChorusActionConfig,
        AudioProcessorDelayActionConfig,
        AudioProcessorReverbActionConfig,
        AudioProcessorNormalizeActionConfig,
        AudioProcessorPeakLimitActionConfig,
        AudioProcessorTrimEdgesActionConfig,
        AudioProcessorTrimSilenceActionConfig,
        AudioProcessorFadeInActionConfig,
        AudioProcessorFadeOutActionConfig,
    ],
    Field(discriminator="method")
]
