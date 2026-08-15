from typing import Union, Literal, Optional, List, Annotated
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioProcessorActionMethod(str, Enum):
    RESAMPLE     = "resample"
    HIGHPASS     = "highpass"
    LOWPASS      = "lowpass"
    BELL         = "bell"
    LOW_SHELF    = "low-shelf"
    HIGH_SHELF   = "high-shelf"
    PITCH_SHIFT  = "pitch-shift"
    DC_SHIFT     = "dc-shift"
    COMPRESSOR   = "compressor"
    NOISE_GATE   = "noise-gate"
    DISTORTION   = "distortion"
    SATURATION   = "saturation"
    GAIN         = "gain"
    CHORUS       = "chorus"
    DELAY        = "delay"
    REVERB       = "reverb"
    NORMALIZE    = "normalize"
    PEAK_LIMIT   = "peak-limit"
    TRIM_EDGES   = "trim-edges"
    TRIM_SILENCE = "trim-silence"
    FADE_IN      = "fade-in"
    FADE_OUT     = "fade-out"
    ANONYMIZE    = "anonymize"

class AudioProcessorNormalizeMode(str, Enum):
    RMS  = "rms"
    PEAK = "peak"
    LUFS = "lufs"

class AudioProcessorPeakLimitMode(str, Enum):
    HARD   = "hard"
    SMOOTH = "smooth"

class CommonAudioProcessorActionConfig(CommonActionConfig):
    method: AudioProcessorActionMethod = Field(..., description="Processing operation this action performs.")
    audio: Union[str, List[str]] = Field(..., description="Input audio to process — a file path, bytes, or variable reference.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")

class AudioProcessorResampleActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.RESAMPLE]
    sample_rate: Union[int, str] = Field(..., description="Target output sample rate in Hz (e.g., 44100, 48000).")

class AudioProcessorHighpassActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.HIGHPASS]
    cutoff: Union[float, str] = Field(..., description="Filter cutoff frequency in Hz.")

class AudioProcessorLowpassActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.LOWPASS]
    cutoff: Union[float, str] = Field(..., description="Filter cutoff frequency in Hz.")

class AudioProcessorBellActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.BELL]
    frequency: Union[float, str] = Field(..., description="Centre frequency of the bell in Hz.")
    gain: Union[float, str] = Field(..., description="Gain at the centre frequency in dB (positive to boost, negative to cut).")
    q: Union[float, str] = Field(default=0.707, description="Bell width; higher Q produces a narrower band.")

class AudioProcessorLowShelfActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.LOW_SHELF]
    frequency: Union[float, str] = Field(..., description="Shelf corner frequency in Hz (audio below this is affected).")
    gain: Union[float, str] = Field(..., description="Shelf gain in dB (positive to boost, negative to cut).")
    q: Union[float, str] = Field(default=0.707, description="Shelf slope; higher Q produces a steeper corner.")

class AudioProcessorHighShelfActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.HIGH_SHELF]
    frequency: Union[float, str] = Field(..., description="Shelf corner frequency in Hz (audio above this is affected).")
    gain: Union[float, str] = Field(..., description="Shelf gain in dB (positive to boost, negative to cut).")
    q: Union[float, str] = Field(default=0.707, description="Shelf slope; higher Q produces a steeper corner.")

class AudioProcessorPitchShiftActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.PITCH_SHIFT]
    semitones: Union[float, str] = Field(..., description="Pitch shift amount in semitones (positive to raise, negative to lower).")

class AudioProcessorDcShiftActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.DC_SHIFT]
    offset: Optional[Union[float, str]] = Field(default=None, description="Additional DC offset applied after centering, from -1.0 to 1.0.")

class AudioProcessorCompressorActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.COMPRESSOR]
    threshold: Union[float, str] = Field(default=-20.0, description="Threshold in dB above which compression applies.")
    ratio: Union[float, str] = Field(default=4.0, description="Compression ratio (e.g., 4.0 for 4:1).")
    attack_time: Union[str, float] = Field(default="1ms", description="Compressor attack time as a duration string (e.g., 1ms) or seconds.")
    release_time: Union[str, float] = Field(default="100ms", description="Compressor release time as a duration string (e.g., 100ms) or seconds.")

class AudioProcessorNoiseGateActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NOISE_GATE]
    threshold: Union[float, str] = Field(default=-40.0, description="Threshold in dB below which the gate attenuates.")
    ratio: Union[float, str] = Field(default=10.0, description="Downward expansion ratio; higher values gate more aggressively.")
    attack_time: Union[str, float] = Field(default="1ms", description="Gate attack time as a duration string (e.g., 1ms) or seconds.")
    release_time: Union[str, float] = Field(default="100ms", description="Gate release time as a duration string (e.g., 100ms) or seconds.")

class AudioProcessorDistortionActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.DISTORTION]
    drive: Union[float, str] = Field(..., description="Drive amount in dB; higher values produce more aggressive distortion (typical range 15 to 40).")

class AudioProcessorSaturationActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.SATURATION]
    drive: Union[float, str] = Field(default=3.0, description="Drive amount in dB for subtle harmonic coloring (typical range 1 to 8).")

class AudioProcessorGainActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.GAIN]
    level: Union[float, str] = Field(..., description="Gain in dB; positive values boost and negative values attenuate.")

class AudioProcessorChorusActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.CHORUS]
    rate: Union[float, str] = Field(default=1.0, description="Chorus LFO rate in Hz.")
    depth: Union[float, str] = Field(default=0.25, description="Modulation depth, from 0.0 to 1.0.")
    feedback: Union[float, str] = Field(default=0.0, description="Feedback amount, from 0.0 to 1.0.")
    delay: Union[str, float] = Field(default="7ms", description="Center delay time as a duration string (e.g., 7ms) or seconds.")
    mix: Union[float, str] = Field(default=0.5, description="Dry/wet mix ratio, from 0.0 (dry) to 1.0 (wet).")

class AudioProcessorDelayActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.DELAY]
    time: Union[str, float] = Field(default="500ms", description="Delay time as a duration string (e.g., 500ms) or seconds.")
    feedback: Union[float, str] = Field(default=0.0, description="Feedback amount, from 0.0 to 1.0.")
    mix: Union[float, str] = Field(default=0.5, description="Dry/wet mix ratio, from 0.0 (dry) to 1.0 (wet).")

class AudioProcessorReverbActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.REVERB]
    room_size: Union[float, str] = Field(default=0.5, description="Simulated room size, from 0.0 to 1.0.")
    damping: Union[float, str] = Field(default=0.5, description="High-frequency damping, from 0.0 to 1.0.")
    wet_level: Union[float, str] = Field(default=0.33, description="Reverberated signal level, from 0.0 to 1.0.")
    dry_level: Union[float, str] = Field(default=0.4, description="Dry signal level, from 0.0 to 1.0.")
    width: Union[float, str] = Field(default=1.0, description="Stereo width of the reverb, from 0.0 to 1.0.")

class AudioProcessorRmsNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    mode: Literal[AudioProcessorNormalizeMode.RMS]
    level: Union[float, str] = Field(default=-20.0, description="Target RMS level in dBFS.")
    peak_limit: Union[float, str] = Field(default=0.85, description="Peak amplitude cap, from 0.0 to 1.0, applied after normalization.")

class AudioProcessorPeakNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    mode: Literal[AudioProcessorNormalizeMode.PEAK]
    level: Union[float, str] = Field(default=-1.0, description="Target peak level in dBFS (e.g., -1.0 leaves 1 dB of headroom).")

class AudioProcessorLufsNormalizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.NORMALIZE]
    mode: Literal[AudioProcessorNormalizeMode.LUFS]
    level: Union[float, str] = Field(default=-14.0, description="Target integrated loudness in LUFS (e.g., -14 for streaming, -9 to -12 for punchier masters).")
    tolerance: Union[float, str] = Field(default=0.5, description="Acceptable deviation from the target in LU before the verify loop re-iterates.")
    max_gain: Union[float, str] = Field(default=30.0, description="Maximum absolute gain in dB the verify loop may apply.")
    true_peak_ceiling: Union[float, str] = Field(default=-1.0, description="True-peak ceiling in dBTP enforced after loudness gain (e.g., -1.0 for -1 dBTP).")

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
    mode: Literal[AudioProcessorPeakLimitMode.HARD]
    level: Union[float, str] = Field(default=0.95, description="Peak amplitude cap, from 0.0 to 1.0; applied only when the input peak exceeds this value.")

class AudioProcessorSmoothPeakLimitActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.PEAK_LIMIT]
    mode: Literal[AudioProcessorPeakLimitMode.SMOOTH]
    level: Union[float, str] = Field(default=-1.0, description="Ceiling in dBFS (e.g., -1.0 leaves 1 dB of headroom).")
    release_time: Union[str, float] = Field(default="100ms", description="Limiter release time as a duration string (e.g., 100ms) or seconds.")

AudioProcessorPeakLimitActionConfig = Annotated[
    Union[
        AudioProcessorHardPeakLimitActionConfig,
        AudioProcessorSmoothPeakLimitActionConfig,
    ],
    Field(discriminator="mode")
]

class AudioProcessorTrimEdgesActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.TRIM_EDGES]
    threshold: Union[float, str] = Field(default=40.0, description="Silence threshold in dB below peak used to detect edge silence.")
    padding: Optional[Union[str, float]] = Field(default=None, description="Padding restored at each edge when trimming shortens the audio (e.g., 100ms).")

class AudioProcessorTrimSilenceActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.TRIM_SILENCE]
    window: Union[str, float] = Field(default="20ms", description="RMS analysis window size as a duration string (e.g., 20ms) or seconds.")
    threshold: Union[float, str] = Field(default=-40.0, description="Silence threshold in dBFS below which a window is treated as silence.")
    min_silence: Union[str, float] = Field(default="200ms", description="Minimum trailing silence to keep (e.g., 200ms).")
    max_internal_silence: Union[str, float] = Field(default="1s", description="Internal silence gaps longer than this are cut from the audio (e.g., 1s).")
    fade: Union[str, float] = Field(default="30ms", description="Cosine fade-out duration applied at the trimmed end (e.g., 30ms).")

class AudioProcessorFadeInActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.FADE_IN]
    duration: Union[str, float] = Field(default="20ms", description="Cosine fade-in duration applied at the start (e.g., 20ms).")

class AudioProcessorFadeOutActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.FADE_OUT]
    duration: Union[str, float] = Field(default="20ms", description="Cosine fade-out duration applied at the end (e.g., 20ms).")

class AudioProcessorAnonymizeActionConfig(CommonAudioProcessorActionConfig):
    method: Literal[AudioProcessorActionMethod.ANONYMIZE]
    pitch_shift: Union[float, str] = Field(default=-2.0, description="Pitch shift in semitones applied to disguise the speaker (positive to raise, negative to lower).")
    formant_shift: Union[float, str] = Field(default=1.15, description="Formant scaling ratio; values >1 shift formants up (perceived smaller vocal tract), <1 shift them down.")
    pitch_jitter: Union[float, str] = Field(default=0.3, description="Random pitch modulation depth in semitones added over time to break speaker-specific prosody.")
    jitter_rate: Union[float, str] = Field(default=4.0, description="Rate of the pitch jitter modulation in Hz.")
    lowpass_cutoff: Optional[Union[float, str]] = Field(default=6000.0, description="Optional low-pass cutoff in Hz applied after anonymization to attenuate high-frequency speaker cues; null to disable.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for reproducible jitter; null for non-deterministic output.")
