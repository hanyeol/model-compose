from typing import Union
from .wav2lip import Wav2LipLipSyncModelActionConfig
from .latentsync import LatentSyncLipSyncModelActionConfig
from .musetalk import MuseTalkLipSyncModelActionConfig

CustomLipSyncModelActionConfig = Union[
    Wav2LipLipSyncModelActionConfig,
    LatentSyncLipSyncModelActionConfig,
    MuseTalkLipSyncModelActionConfig,
]
