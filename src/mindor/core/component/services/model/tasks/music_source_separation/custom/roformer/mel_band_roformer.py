from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type
from mindor.dsl.schema.component import MelBandRoFormerMusicSourceSeparationModelComponentConfig
from .base import RoFormerMusicSourceSeparationTaskDriver

if TYPE_CHECKING:
    import torch

class MelBandRoFormerMusicSourceSeparationTaskDriver(RoFormerMusicSourceSeparationTaskDriver):
    config: MelBandRoFormerMusicSourceSeparationModelComponentConfig

    def __init__(self, id: str, config: MelBandRoFormerMusicSourceSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_model_class(self) -> Type[torch.nn.Module]:
        from bs_roformer import MelBandRoformer
        return MelBandRoformer

    def _get_sample_rate(self) -> int:
        # Mel-band's mel filter bank is built for this rate at model
        # construction time; audio must be resampled to match.
        return self.config.params.sample_rate
