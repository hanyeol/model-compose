from mindor.dsl.schema.component import ModelComponentConfig, TalkingHeadModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TALKING_HEAD, ModelDriverType.CUSTOM)
class CustomTalkingHeadTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == TalkingHeadModelFamily.SADTALKER:
            from .sadtalker import SadTalkerTalkingHeadTaskDriver
            return SadTalkerTalkingHeadTaskDriver(id, config, daemon)

        if config.family == TalkingHeadModelFamily.HALLO2:
            from .hallo2 import Hallo2TalkingHeadTaskDriver
            return Hallo2TalkingHeadTaskDriver(id, config, daemon)

        if config.family == TalkingHeadModelFamily.HALLO3:
            from .hallo3 import Hallo3TalkingHeadTaskDriver
            return Hallo3TalkingHeadTaskDriver(id, config, daemon)

        if config.family == TalkingHeadModelFamily.SONIC:
            from .sonic import SonicTalkingHeadTaskDriver
            return SonicTalkingHeadTaskDriver(id, config, daemon)

        if config.family == TalkingHeadModelFamily.ECHOMIMIC:
            from .echomimic import EchoMimicTalkingHeadTaskDriver
            return EchoMimicTalkingHeadTaskDriver(id, config, daemon)

        if config.family == TalkingHeadModelFamily.FLOAT:
            from .float import FloatTalkingHeadTaskDriver
            return FloatTalkingHeadTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
