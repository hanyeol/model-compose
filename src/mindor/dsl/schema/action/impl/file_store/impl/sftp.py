from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonFilePutActionConfig,
    CommonFileGetActionConfig,
    CommonFileDeleteActionConfig,
    CommonFileExistsActionConfig,
    CommonFileListActionConfig,
)

class SftpFilePutActionConfig(CommonFilePutActionConfig):
    pass

class SftpFileGetActionConfig(CommonFileGetActionConfig):
    pass

class SftpFileDeleteActionConfig(CommonFileDeleteActionConfig):
    pass

class SftpFileExistsActionConfig(CommonFileExistsActionConfig):
    pass

class SftpFileListActionConfig(CommonFileListActionConfig):
    pass

SftpFileStoreActionConfig = Annotated[
    Union[
        SftpFilePutActionConfig,
        SftpFileGetActionConfig,
        SftpFileDeleteActionConfig,
        SftpFileExistsActionConfig,
        SftpFileListActionConfig,
    ],
    Field(discriminator="method")
]
