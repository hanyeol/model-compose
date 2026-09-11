from typing import Union, Annotated
from pydantic import Field
from .sadtalker import SadTalkerTalkingHeadModelComponentConfig
from .hallo2 import Hallo2TalkingHeadModelComponentConfig
from .hallo3 import Hallo3TalkingHeadModelComponentConfig
from .sonic import SonicTalkingHeadModelComponentConfig
from .echomimic import EchoMimicTalkingHeadModelComponentConfig
from .float import FloatTalkingHeadModelComponentConfig

CustomTalkingHeadModelComponentConfig = Annotated[
    Union[
        SadTalkerTalkingHeadModelComponentConfig,
        Hallo2TalkingHeadModelComponentConfig,
        Hallo3TalkingHeadModelComponentConfig,
        SonicTalkingHeadModelComponentConfig,
        EchoMimicTalkingHeadModelComponentConfig,
        FloatTalkingHeadModelComponentConfig,
    ],
    Field(discriminator="family")
]
