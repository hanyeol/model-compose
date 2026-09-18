from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type
from mindor.dsl.schema.component import BsRoFormerMusicSourceSeparationModelComponentConfig
from .base import RoFormerMusicSourceSeparationTaskDriver

if TYPE_CHECKING:
    import torch

# BS-RoFormer's STFT is sample-rate agnostic; the community checkpoints are
# trained on 44.1 kHz mixes so the wrapper feeds audio at that rate.
_BS_ROFORMER_SAMPLE_RATE = 44100

class BsRoFormerMusicSourceSeparationTaskDriver(RoFormerMusicSourceSeparationTaskDriver):
    config: BsRoFormerMusicSourceSeparationModelComponentConfig

    def __init__(self, id: str, config: BsRoFormerMusicSourceSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_model_class(self) -> Type[torch.nn.Module]:
        from bs_roformer import BSRoformer
        return BSRoformer

    def _get_sample_rate(self) -> int:
        return _BS_ROFORMER_SAMPLE_RATE
