from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import Mdx23cMusicSourceSeparationModelActionConfig
from ..common import CommonMusicSourceSeparationModelComponentConfig
from .common import MusicSourceSeparationModelFamily
from ....common import ModelDriverType, ModelConfig

class Mdx23cMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.MDX_23C]
    model: ModelConfig = Field(..., description="Model checkpoint (.ckpt) — a HuggingFace repo file, a URL, or a local path.")
    instruments: List[str] = Field(..., description="Output stem names, in the order the checkpoint emits them.")
    target_instrument: Optional[str] = Field(default=None, description="If set, the checkpoint predicts only this single stem instead of all instruments.")
    n_fft: int = Field(default=2048, description="STFT window size used at training time; must match the checkpoint.")
    hop_length: int = Field(default=512, description="STFT hop length used at training time; must match the checkpoint.")
    dim_f: int = Field(default=1024, description="Number of frequency bins fed to the network; determines the first-layer input width.")
    num_subbands: int = Field(default=4, description="Sub-band split factor along the frequency axis.")
    num_scales: int = Field(default=5, description="Encoder/decoder depth (number of down/up-scale stages).")
    num_blocks_per_scale: int = Field(default=2, description="TFC-TDF blocks per encoder/decoder stage.")
    num_channels: int = Field(default=128, description="Base convolutional channel count.")
    growth: int = Field(default=128, description="Channel growth per encoder stage.")
    bottleneck_factor: int = Field(default=4, description="Bottleneck reduction inside each TDF block.")
    actions: List[Mdx23cMusicSourceSeparationModelActionConfig] = Field(default_factory=list, description="Actions this music source separation component exposes to workflows.")
