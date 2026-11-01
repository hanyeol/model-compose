from typing import Union, Annotated
from pydantic import Field
from .impl import *

RemoteTransportConfig = Annotated[
    Union[
        SshRemoteTransportConfig,
        TailscaleRemoteTransportConfig,
    ],
    Field(discriminator="type")
]
