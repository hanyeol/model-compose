from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import MelBandRoFormerMusicSourceSeparationModelActionConfig, MusicSourceSeparationStem
from ...common import CommonMusicSourceSeparationModelComponentConfig
from ..common import MusicSourceSeparationModelFamily
from .common import CommonRoFormerModelParamsConfig
from .....common import ModelDriverType, ModelConfig

class MelBandRoFormerModelParamsConfig(CommonRoFormerModelParamsConfig):
    num_bands: int = Field(default=60, description="Number of mel bands the encoder splits the spectrogram into.")
    sample_rate: int = Field(default=44100, description="Sample rate the mel filter bank is built for; must match the audio fed to the model.")

class MelBandRoFormerMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.MEL_BAND_ROFORMER]
    model: ModelConfig = Field(..., description="Checkpoint identifier — a HuggingFace repo ID or a local path; set `filename` to pick a specific .ckpt/.safetensors file within the repo.")
    stems: Optional[List[Union[MusicSourceSeparationStem, str]]] = Field(default=None, description="Names of the stems this checkpoint produces, in output order; falls back to `stem_0`, `stem_1`, ... when omitted.")
    params: MelBandRoFormerModelParamsConfig = Field(..., description="Architecture hyperparameters forwarded to `bs_roformer.MelBandRoformer(...)`; must match the checkpoint.")
    actions: List[MelBandRoFormerMusicSourceSeparationModelActionConfig] = Field(default_factory=list, description="Actions this music source separation component exposes to workflows.")
