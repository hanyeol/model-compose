from typing import Union, Annotated
from pydantic import Field
from .impl import *

SystemConfig = Annotated[
    Union[
        DockerComposeSystemConfig,
    ],
    Field(discriminator="type")
]
