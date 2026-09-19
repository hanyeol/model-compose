from mindor.dsl.schema.component import ModelComponentConfig, MusicSourceSeparationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_SOURCE_SEPARATION, ModelDriverType.CUSTOM)
class CustomMusicSourceSeparationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicSourceSeparationModelFamily.DEMUCS:
            from .demucs import DemucsMusicSourceSeparationTaskDriver
            return DemucsMusicSourceSeparationTaskDriver(id, config, daemon)

        if config.family == MusicSourceSeparationModelFamily.MDX_NET:
            from .mdx_net import MdxNetMusicSourceSeparationTaskDriver
            return MdxNetMusicSourceSeparationTaskDriver(id, config, daemon)

        if config.family == MusicSourceSeparationModelFamily.MDX23C:
            from .mdx23c import Mdx23cMusicSourceSeparationTaskDriver
            return Mdx23cMusicSourceSeparationTaskDriver(id, config, daemon)

        if config.family == MusicSourceSeparationModelFamily.BS_ROFORMER:
            from .roformer.bs_roformer import BsRoFormerMusicSourceSeparationTaskDriver
            return BsRoFormerMusicSourceSeparationTaskDriver(id, config, daemon)

        if config.family == MusicSourceSeparationModelFamily.MEL_BAND_ROFORMER:
            from .roformer.mel_band_roformer import MelBandRoFormerMusicSourceSeparationTaskDriver
            return MelBandRoFormerMusicSourceSeparationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
