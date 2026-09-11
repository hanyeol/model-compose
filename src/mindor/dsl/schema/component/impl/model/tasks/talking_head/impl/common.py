from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonTalkingHeadModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TALKING_HEAD]
