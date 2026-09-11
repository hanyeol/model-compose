from typing import Union
from .sadtalker import SadTalkerTalkingHeadModelActionConfig
from .hallo2 import Hallo2TalkingHeadModelActionConfig
from .hallo3 import Hallo3TalkingHeadModelActionConfig
from .sonic import SonicTalkingHeadModelActionConfig
from .echomimic import EchoMimicTalkingHeadModelActionConfig
from .float import FloatTalkingHeadModelActionConfig

CustomTalkingHeadModelActionConfig = Union[
    SadTalkerTalkingHeadModelActionConfig,
    Hallo2TalkingHeadModelActionConfig,
    Hallo3TalkingHeadModelActionConfig,
    SonicTalkingHeadModelActionConfig,
    EchoMimicTalkingHeadModelActionConfig,
    FloatTalkingHeadModelActionConfig,
]
