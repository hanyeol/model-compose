from mindor.dsl.schema.component import ModelComponentConfig, TalkingHeadModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.TALKING_HEAD, ModelDriver.CUSTOM)
class CustomTalkingHeadTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == TalkingHeadModelFamily.SADTALKER:
            from .sadtalker import SadTalkerTalkingHeadTaskService
            return SadTalkerTalkingHeadTaskService(id, config, daemon)

        if config.family == TalkingHeadModelFamily.HALLO2:
            from .hallo2 import Hallo2TalkingHeadTaskService
            return Hallo2TalkingHeadTaskService(id, config, daemon)

        if config.family == TalkingHeadModelFamily.HALLO3:
            from .hallo3 import Hallo3TalkingHeadTaskService
            return Hallo3TalkingHeadTaskService(id, config, daemon)

        if config.family == TalkingHeadModelFamily.SONIC:
            from .sonic import SonicTalkingHeadTaskService
            return SonicTalkingHeadTaskService(id, config, daemon)

        if config.family == TalkingHeadModelFamily.ECHOMIMIC:
            from .echomimic import EchoMimicTalkingHeadTaskService
            return EchoMimicTalkingHeadTaskService(id, config, daemon)

        if config.family == TalkingHeadModelFamily.FLOAT:
            from .float import FloatTalkingHeadTaskService
            return FloatTalkingHeadTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
