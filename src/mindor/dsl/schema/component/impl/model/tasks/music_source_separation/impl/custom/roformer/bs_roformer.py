from typing import Literal, List, Optional, Tuple, Union
from pydantic import Field
from mindor.dsl.schema.action import BsRoFormerMusicSourceSeparationModelActionConfig, MusicSourceSeparationStem
from ...common import CommonMusicSourceSeparationModelComponentConfig
from ..common import MusicSourceSeparationModelFamily
from .common import CommonRoFormerModelParamsConfig
from .....common import ModelDriverType, ModelConfig

class BsRoFormerModelParamsConfig(CommonRoFormerModelParamsConfig):
    freqs_per_bands: Optional[Tuple[int, ...]] = Field(default=None, description="Frequency-bin counts per band; must sum to the STFT bin count. When omitted the model uses lucidrains' default 62-band split.")

class BsRoFormerMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.BS_ROFORMER]
    model: ModelConfig = Field(..., description="Checkpoint identifier — a HuggingFace repo ID or a local path; set `filename` to pick a specific .ckpt/.safetensors file within the repo.")
    stems: Optional[List[Union[MusicSourceSeparationStem, str]]] = Field(default=None, description="Names of the stems this checkpoint produces, in output order; falls back to `stem_0`, `stem_1`, ... when omitted.")
    params: BsRoFormerModelParamsConfig = Field(..., description="Architecture hyperparameters forwarded to `bs_roformer.BSRoformer(...)`; must match the checkpoint.")
    actions: List[BsRoFormerMusicSourceSeparationModelActionConfig] = Field(default_factory=list, description="Actions this music source separation component exposes to workflows.")
