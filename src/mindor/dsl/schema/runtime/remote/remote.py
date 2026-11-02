from typing import Union, Annotated
from pydantic import Field
from .impl import *

RemoteTransportConfig = Annotated[
    Union[
        SshRemoteTransportConfig,
    ],
    Field(discriminator="type")
]
