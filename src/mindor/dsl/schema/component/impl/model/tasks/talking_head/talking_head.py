from typing import Union, Annotated
from pydantic import Field
from .impl import *

TalkingHeadModelComponentConfig = Annotated[
    Union[
        CustomTalkingHeadModelComponentConfig,
    ],
    Field(discriminator="driver")
]
