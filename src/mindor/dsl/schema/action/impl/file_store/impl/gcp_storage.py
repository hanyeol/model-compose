from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonFilePutActionConfig,
    CommonFileGetActionConfig,
    CommonFileDeleteActionConfig,
    CommonFileExistsActionConfig,
    CommonFileListActionConfig,
)

class GcpStorageFilePutActionConfig(CommonFilePutActionConfig):
    pass

class GcpStorageFileGetActionConfig(CommonFileGetActionConfig):
    pass

class GcpStorageFileDeleteActionConfig(CommonFileDeleteActionConfig):
    pass

class GcpStorageFileExistsActionConfig(CommonFileExistsActionConfig):
    pass

class GcpStorageFileListActionConfig(CommonFileListActionConfig):
    pass

GcpStorageFileStoreActionConfig = Annotated[
    Union[
        GcpStorageFilePutActionConfig,
        GcpStorageFileGetActionConfig,
        GcpStorageFileDeleteActionConfig,
        GcpStorageFileExistsActionConfig,
        GcpStorageFileListActionConfig,
    ],
    Field(discriminator="method")
]
