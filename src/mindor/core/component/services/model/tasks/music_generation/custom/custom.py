from mindor.dsl.schema.component import ModelComponentConfig, MusicGenerationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_GENERATION, ModelDriverType.CUSTOM)
class CustomMusicGenerationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicGenerationModelFamily.ACE_STEP:
            from .ace_step import AceStepMusicGenerationTaskDriver
            return AceStepMusicGenerationTaskDriver(id, config, daemon)

        if config.family == MusicGenerationModelFamily.MIDI_DDSP:
            from .midi_ddsp import MidiDdspMusicGenerationTaskDriver
            return MidiDdspMusicGenerationTaskDriver(id, config, daemon)

        if config.family == MusicGenerationModelFamily.YUE2:
            from .yue2 import Yue2MusicGenerationTaskDriver
            return Yue2MusicGenerationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
