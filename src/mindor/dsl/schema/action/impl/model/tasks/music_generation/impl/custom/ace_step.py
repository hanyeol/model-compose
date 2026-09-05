from typing import Union, Literal, Optional, List, Annotated
from enum import Enum
from pydantic import Field
from ..common import (
    CommonMusicGenerationParamsConfig,
    CommonMusicGenerationModelActionConfig,
    MusicGenerationActionMethod,
)

class AceStepTrackClass(str, Enum):
    WOODWINDS       = "woodwinds"
    BRASS           = "brass"
    FX              = "fx"
    SYNTH           = "synth"
    STRINGS         = "strings"
    PERCUSSION      = "percussion"
    KEYBOARD        = "keyboard"
    GUITAR          = "guitar"
    BASS            = "bass"
    DRUMS           = "drums"
    BACKING_VOCALS  = "backing-vocals"
    VOCALS          = "vocals"

class AceStepMusicGenerationParamsConfig(CommonMusicGenerationParamsConfig):
    time_signature: Optional[str] = Field(default="4/4", description="Musical time signature of the generated music (e.g., 4/4, 3/4).")
    inference_steps: Union[int, str] = Field(default=8, description="Number of diffusion inference steps (turbo: 8, base: 32, sft: 50).")
    guidance_scale: Union[float, str] = Field(default=5.0, description="Classifier-free guidance scale applied during sampling.")
    shift: Union[float, str] = Field(default=1.0, description="Flow-matching timestep shift (turbo: 1.0, base/sft: 3.0).")
    use_adg: Union[bool, str] = Field(default=False, description="Whether to enable ADG (angle-based dynamic guidance); recommended for base/sft presets.")

class CommonAceStepMusicGenerationModelActionConfig(CommonMusicGenerationModelActionConfig):
    params: AceStepMusicGenerationParamsConfig = Field(default_factory=AceStepMusicGenerationParamsConfig, description="ACE-Step music generation parameters.")

class AceStepMusicGenerationModelGenerateActionConfig(CommonAceStepMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.GENERATE]
    prompt: Union[str, List[str]] = Field(..., description="Text description of the music style, genre, mood, and instrumentation.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Song lyrics used for vocal generation.")
    reference_audio: Optional[str] = Field(default=None, description="Optional reference audio guiding timbre, mixing, and performance style.")

class AceStepMusicGenerationModelCoverActionConfig(CommonAceStepMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.COVER]
    source: str = Field(..., description="Source audio to create a cover from.")
    prompt: Union[str, List[str]] = Field(..., description="Text description of the target cover style.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Optional lyrics to sing in the cover.")

class AceStepMusicGenerationModelRewriteActionConfig(CommonAceStepMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.REWRITE]
    source: str = Field(..., description="Source audio containing the region to rewrite.")
    start_time: Union[float, str] = Field(..., description="Start time in seconds of the region to regenerate.")
    end_time: Union[float, str] = Field(..., description="End time in seconds of the region to regenerate.")
    prompt: Union[str, List[str]] = Field(..., description="Text description guiding the rewritten region.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Optional lyrics for the rewritten region.")

class AceStepMusicGenerationModelExtendActionConfig(CommonAceStepMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.EXTEND]
    source: str = Field(..., description="Source audio to continue past its end.")
    prompt: Union[str, List[str]] = Field(..., description="Text description of the continuation style.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Optional lyrics for the continuation.")

class AceStepMusicGenerationModelLayerActionConfig(CommonAceStepMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.LAYER]
    source: str = Field(..., description="Source audio to layer a new track on top of.")
    track_class: AceStepTrackClass = Field(..., description="Stem to generate on top of the source (e.g., drums, bass, vocals).")
    prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Text description guiding the added layer.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Optional lyrics when the added layer is vocals.")

class AceStepMusicGenerationModelAccompanyActionConfig(CommonAceStepMusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.ACCOMPANY]
    vocal: str = Field(..., description="Vocal-only audio to generate accompaniment for.")
    track_classes: List[AceStepTrackClass] = Field(..., min_length=1, description="Stem classes to fill in as accompaniment (e.g., drums, bass, keyboard).")
    prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Text description of the desired accompaniment style.")

AceStepMusicGenerationModelActionConfig = Annotated[
    Union[
        AceStepMusicGenerationModelGenerateActionConfig,
        AceStepMusicGenerationModelCoverActionConfig,
        AceStepMusicGenerationModelRewriteActionConfig,
        AceStepMusicGenerationModelExtendActionConfig,
        AceStepMusicGenerationModelLayerActionConfig,
        AceStepMusicGenerationModelAccompanyActionConfig,
    ],
    Field(discriminator="method")
]
